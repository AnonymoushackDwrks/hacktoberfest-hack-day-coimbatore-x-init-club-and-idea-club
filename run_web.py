#!/usr/bin/env python3
"""Entrypoint script for OctoGemma Web Studio."""

import uvicorn
from src.octogemma.config import settings

if __name__ == "__main__":
    print(f"Starting OctoGemma Web Studio at http://{settings.web_host}:{settings.web_port}")
    uvicorn.run("src.octogemma.server:app", host=settings.web_host, port=settings.web_port, reload=True)
