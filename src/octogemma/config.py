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


settings = Settings()
