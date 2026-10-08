"""Configuration management for OctoGemma."""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


class Settings(BaseModel):
    """Runtime configuration settings."""
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    )
    default_model: str = Field(
        default_factory=lambda: os.getenv("OCTOGEMMA_MODEL", "gemma4:e4b")
    )
    max_steps: int = Field(
        default_factory=lambda: int(os.getenv("OCTOGEMMA_MAX_STEPS", "25"))
    )
    timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("OCTOGEMMA_TIMEOUT_SECONDS", "120"))
    )
    workspace_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("OCTOGEMMA_WORKSPACE", ".")).resolve()
    )
    web_host: str = Field(
        default_factory=lambda: os.getenv("WEB_HOST", "127.0.0.1")
    )
    web_port: int = Field(
        default_factory=lambda: int(os.getenv("WEB_PORT", "8000"))
    )


    custom_models_file: Path = Field(
        default_factory=lambda: Path(os.getenv("OCTOGEMMA_CONFIG_DIR", ".")).resolve() / ".octogemma_models.json"
    )


settings = Settings()


def get_custom_models() -> list[dict]:
    """Retrieve saved custom local models."""
    if not settings.custom_models_file.exists():
        return []
    try:
        import json
        with open(settings.custom_models_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_custom_model(model_entry: dict) -> list[dict]:
    """Add or update a custom local model entry."""
    import json
    current = get_custom_models()
    # Check if already exists
    name = model_entry.get("name")
    filtered = [m for m in current if m.get("name") != name]
    filtered.append(model_entry)
    try:
        with open(settings.custom_models_file, "w", encoding="utf-8") as f:
            json.dump(filtered, f, indent=2)
    except Exception:
        pass
    return filtered


def delete_custom_model(model_name: str) -> list[dict]:
    """Remove a custom model entry."""
    import json
    current = get_custom_models()
    filtered = [m for m in current if m.get("name") != model_name]
    try:
        with open(settings.custom_models_file, "w", encoding="utf-8") as f:
            json.dump(filtered, f, indent=2)
    except Exception:
        pass
    return filtered
