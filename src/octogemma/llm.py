"""Ollama client and LLM communication interface for OctoGemma."""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx
from .config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Interface to communicate with the local Ollama daemon."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")

    async def check_health(self) -> bool:
        """Check if local Ollama server is responsive."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[Dict[str, Any]]:
        """List all locally installed models."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    return data.get("models", [])
                return []
        except Exception as e:
            logger.error("Failed to list models: %s", e)
            return []

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

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Non-streaming chat completion request with optional tool schema."""
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_ctx": 16384,  # Expanded context window for agent reasoning
            },
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
            res = await client.post(f"{self.base_url}/api/chat", json=payload)
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
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_ctx": 16384,
            },
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    err_msg = await resp.aread()
                    raise RuntimeError(f"Ollama stream error {resp.status_code}: {err_msg.decode('utf-8')}")

                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        yield chunk
                    except Exception:
                        pass
