"""Unit tests for Local LLM management and custom model registration."""

import pytest
from pathlib import Path
from src.octogemma.config import settings, get_custom_models, save_custom_model, delete_custom_model
from src.octogemma.llm import OllamaClient


def test_custom_models_persistence(tmp_path: Path):
    test_file = tmp_path / "test_models.json"
    settings.custom_models_file = test_file

    assert get_custom_models() == []

    # Add model
    saved = save_custom_model({"name": "my-qwen-coder:latest", "family": "qwen"})
    assert len(saved) == 1
    assert saved[0]["name"] == "my-qwen-coder:latest"

    # Retrieve
    models = get_custom_models()
    assert len(models) == 1
    assert models[0]["name"] == "my-qwen-coder:latest"

    # Add another
    saved = save_custom_model({"name": "custom-deepseek:8b", "family": "deepseek"})
    assert len(saved) == 2

    # Delete
    deleted = delete_custom_model("my-qwen-coder:latest")
    assert len(deleted) == 1
    assert deleted[0]["name"] == "custom-deepseek:8b"

    # Reset
    settings.custom_models_file = Path(".octogemma_models.json")


def test_ollama_client_set_base_url():
    client = OllamaClient("http://localhost:11434")
    client.set_base_url("http://127.0.0.1:11435")
    assert client.base_url == "http://127.0.0.1:11435"
    assert settings.ollama_base_url == "http://127.0.0.1:11435"
    client.set_base_url("http://localhost:11434")
