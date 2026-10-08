"""Ollama client and LLM communication interface for OctoGemma."""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx
from .config import settings, get_custom_models

logger = logging.getLogger(__name__)


class OllamaClient:
    """Interface to communicate with the local Ollama daemon."""

    def __init__(self, base_url: Optional[str] = None):
        url = (base_url or settings.ollama_base_url).rstrip("/")
        if "localhost" in url:
            url = url.replace("localhost", "127.0.0.1")
        self.base_url = url

    def set_base_url(self, base_url: str):
        """Update the base URL for Ollama / local LLM server."""
        url = base_url.rstrip("/")
        if "localhost" in url:
            url = url.replace("localhost", "127.0.0.1")
        self.base_url = url
        settings.ollama_base_url = self.base_url

    async def check_health(self) -> bool:
        """Check if local Ollama server is responsive."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def show_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Fetch details about a model from Ollama."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(f"{self.base_url}/api/show", json={"name": model_name})
                if res.status_code == 200:
                    return res.json()
                return None
        except Exception:
            return None

    async def list_models(self) -> List[Dict[str, Any]]:
        """List all locally installed and custom registered models."""
        models: List[Dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = data.get("models", [])
        except Exception as e:
            logger.error("Failed to list models: %s", e)

        # Merge saved custom models that may not yet be in Ollama's active tags
        existing_names = {m.get("name") for m in models}
        for cm in get_custom_models():
            cname = cm.get("name")
            if cname and cname not in existing_names:
                models.append({
                    "name": cname,
                    "size": cm.get("size", 0),
                    "modified_at": cm.get("created_at", ""),
                    "is_custom": True,
                    "details": {
                        "family": cm.get("family", "custom"),
                        "format": cm.get("format", "custom"),
                        "parameter_size": cm.get("parameter_size", "custom")
                    }
                })
                existing_names.add(cname)

        return models

    async def get_preferred_model(self, requested: Optional[str] = None) -> str:
        """Select requested model or pick best available coding model."""
        target = requested or settings.default_model
        models = await self.list_models()
        model_names = [m.get("name", "") for m in models]

        # Exact match or prefix match (e.g., 'gemma4:e4b' or 'gemma4')
        for name in model_names:
            if target == name or name.startswith(target):
                return name

        # If requested target is not found, prioritize sensible fallbacks
        priority = [
            "gemma4:e4b",
            "gemma4:12b",
            "gemma4",
            "deepseek-coder-v2:16b-lite-instruct-q4_0",
            "deepseek-coder-v2",
            "qwen3-coder:30b-a3b-q4_K_M",
            "qwen3-coder",
        ]
        for p in priority:
            for name in model_names:
                if p == name or name.startswith(p):
                    return name

        # If any model exists, return the first one
        if model_names:
            return model_names[0]

        return target

    async def pull_model_stream(self, model_name: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream progress while pulling an Ollama model."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0)) as client:
            payload = {"name": model_name, "stream": True}
            async with client.stream("POST", f"{self.base_url}/api/pull", json=payload) as resp:
                if resp.status_code != 200:
                    error_text = await resp.aread()
                    yield {"status": "error", "error": f"HTTP {resp.status_code}: {error_text.decode('utf-8')}"}
                    return

                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        yield chunk
                    except Exception:
                        pass

    async def create_model_stream(self, name: str, modelfile: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream progress while creating/importing an Ollama model from a Modelfile or GGUF."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0)) as client:
            payload = {"name": name, "modelfile": modelfile, "stream": True}
            async with client.stream("POST", f"{self.base_url}/api/create", json=payload) as resp:
                if resp.status_code != 200:
                    error_text = await resp.aread()
                    yield {"status": "error", "error": f"HTTP {resp.status_code}: {error_text.decode('utf-8')}"}
                    return

                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        yield chunk
                    except Exception:
                        pass

    _unsupported_models: set = set()

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Non-streaming chat completion request with automatic tool fallback and adaptive context size."""
        m_lower = model.lower()
        if any(tag in m_lower for tag in ("1.5b", "1b", "2b", "3b", "e4b")):
            num_ctx = 4096
            num_predict = 768
        elif any(tag in m_lower for tag in ("7b", "8b", "12b", "14b", "16b")):
            num_ctx = 8192
            num_predict = 1024
        else:
            num_ctx = 16384
            num_predict = 1536

        send_tools = tools if (tools and model not in self._unsupported_models) else None

        options: Dict[str, Any] = {
            "temperature": temperature,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": options,
        }
        if send_tools:
            payload["tools"] = send_tools

        timeout_cfg = httpx.Timeout(
            connect=15.0,
            read=float(settings.timeout_seconds),
            write=30.0,
            pool=15.0
        )

        async with httpx.AsyncClient(timeout=timeout_cfg) as client:
            try:
                res = await client.post(f"{self.base_url}/api/chat", json=payload)
            except httpx.TimeoutException as te:
                raise TimeoutError(f"Ollama request timed out after {settings.timeout_seconds}s for model '{model}'. Consider setting a higher OCTOGEMMA_TIMEOUT_SECONDS or using a lighter model.") from te
            except httpx.ConnectError as ce:
                raise ConnectionError(f"Cannot connect to Ollama at {self.base_url}. Verify that 'ollama serve' is running.") from ce

            if res.status_code == 400 and ("does not support tools" in res.text or "not support" in res.text):
                logger.info(f"Model '{model}' does not support native tools schema. Retrying in ReAct prompt mode.")
                self._unsupported_models.add(model)
                payload.pop("tools", None)
                try:
                    res = await client.post(f"{self.base_url}/api/chat", json=payload)
                except httpx.TimeoutException as te:
                    raise TimeoutError(f"Ollama request timed out after {settings.timeout_seconds}s during prompt retry for model '{model}'.") from te

            if res.status_code != 200:
                raise RuntimeError(f"Ollama error {res.status_code}: {res.text}")
            return res.json()

    async def chat_stream(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream chat tokens from Ollama."""
        m_lower = model.lower()
        if any(tag in m_lower for tag in ("1.5b", "1b", "2b", "3b", "e4b")):
            num_ctx = 4096
            num_predict = 1024
        elif any(tag in m_lower for tag in ("7b", "8b", "12b", "14b", "16b")):
            num_ctx = 8192
            num_predict = 1536
        else:
            num_ctx = 16384
            num_predict = 2048

        send_tools = tools if (tools and model not in self._unsupported_models) else None

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
        }
        if send_tools:
            payload["tools"] = send_tools

        timeout_cfg = httpx.Timeout(
            connect=15.0,
            read=float(settings.timeout_seconds),
            write=30.0,
            pool=15.0
        )

        async with httpx.AsyncClient(timeout=timeout_cfg) as client:
            try:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                    if resp.status_code == 400 and ("does not support tools" in (await resp.aread()).decode() or "not support" in (await resp.aread()).decode()):
                        self._unsupported_models.add(model)
                        payload.pop("tools", None)
                        async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as retry_resp:
                            if retry_resp.status_code != 200:
                                err_msg = await retry_resp.aread()
                                raise RuntimeError(f"Ollama stream error {retry_resp.status_code}: {err_msg.decode('utf-8')}")
                            async for line in retry_resp.aiter_lines():
                                if not line.strip():
                                    continue
                                try:
                                    yield json.loads(line)
                                except Exception:
                                    pass
                        return

                    if resp.status_code != 200:
                        err_msg = await resp.aread()
                        raise RuntimeError(f"Ollama stream error {resp.status_code}: {err_msg.decode('utf-8')}")

                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            yield json.loads(line)
                        except Exception:
                            pass
            except httpx.TimeoutException as te:
                raise TimeoutError(f"Ollama stream timed out after {settings.timeout_seconds}s for model '{model}'.") from te
            except httpx.ConnectError as ce:
                raise ConnectionError(f"Cannot connect to Ollama at {self.base_url}.") from ce
