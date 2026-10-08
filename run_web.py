#!/usr/bin/env python3
"""Entrypoint script for OctoGemma Web Studio."""

import uvicorn
from src.octogemma.config import settings

if __name__ == "__main__":
    print()
    print("  +----------------------------------------------------+")
    print("  |           OctoGemma Web Studio                      |")
    print("  +----------------------------------------------------+")
    print(f"  |  Web UI:   http://{settings.web_host}:{settings.web_port}")
    print(f"  |  Ollama:   {settings.ollama_base_url}")
    print(f"  |  Model:    {settings.default_model}")
    print("  +----------------------------------------------------+")
    print()
    uvicorn.run("src.octogemma.server:app", host=settings.web_host, port=settings.web_port, reload=True)

