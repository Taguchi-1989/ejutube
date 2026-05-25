from __future__ import annotations

import os

from .base import LLMBackend, OllamaUnavailableError
from .anthropic_backend import AnthropicBackend
from .ollama_backend import OllamaBackend


def get_backend(name: str | None = None) -> LLMBackend:
    chosen = (name or os.environ.get("EJUTUBE_LLM_BACKEND", "ollama")).lower()
    if chosen == "anthropic":
        return AnthropicBackend()
    if chosen == "ollama":
        return OllamaBackend()
    raise ValueError(f"Unknown LLM backend: {chosen!r} (expected 'ollama' or 'anthropic')")


__all__ = [
    "LLMBackend",
    "OllamaUnavailableError",
    "AnthropicBackend",
    "OllamaBackend",
    "get_backend",
]
