"""Tests for the LLM backend abstraction."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pipeline.translation.backends import (
    OllamaBackend,
    AnthropicBackend,
    OllamaUnavailableError,
    get_backend,
)


def test_get_backend_defaults_to_ollama(monkeypatch):
    monkeypatch.delenv("EJUTUBE_LLM_BACKEND", raising=False)
    b = get_backend()
    assert b.name == "ollama"


def test_get_backend_anthropic_via_env(monkeypatch):
    monkeypatch.setenv("EJUTUBE_LLM_BACKEND", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    b = get_backend()
    assert b.name == "anthropic"


def test_get_backend_explicit_arg():
    assert get_backend("ollama").name == "ollama"


def test_get_backend_rejects_unknown():
    with pytest.raises(ValueError):
        get_backend("madeup")


def test_ollama_backend_chat_happy_path(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "gemma4:e4b")
    backend = OllamaBackend()

    async def fake_post(self, url, json):  # noqa: A002
        assert url.endswith("/api/chat")
        assert json["model"] == "gemma4:e4b"
        assert json["stream"] is False
        assert json["messages"][0]["role"] == "system"
        assert json["options"]["temperature"] == 0.5
        assert json["options"]["num_predict"] == 123

        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"message": {"content": "  こんにちは  "}})
        return resp

    with patch.object(httpx.AsyncClient, "post", new=fake_post):
        out = asyncio.run(
            backend.chat(system="sys", user="hi", max_tokens=123, temperature=0.5)
        )
    assert out == "こんにちは"


def test_ollama_backend_raises_on_connection_refused():
    backend = OllamaBackend(endpoint="http://127.0.0.1:1")  # nothing listening

    async def fake_post(self, url, json):  # noqa: A002
        raise httpx.ConnectError("refused")

    with patch.object(httpx.AsyncClient, "post", new=fake_post):
        with pytest.raises(OllamaUnavailableError):
            asyncio.run(backend.chat(system="s", user="u"))


def test_anthropic_backend_name():
    b = AnthropicBackend(model="claude-test")
    assert b.name == "anthropic"
    assert b.model == "claude-test"
