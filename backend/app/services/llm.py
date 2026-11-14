"""Thin wrapper around the configured LLM provider (Ollama locally by default)."""
from backend.app.core.config import settings


def generate(prompt: str) -> str:
    # TODO: call Ollama (http://localhost:11434) or cloud provider per settings.LLM_PROVIDER
    return f"[{settings.LLM_PROVIDER}:{settings.LLM_MODEL}] LLM not wired yet."
