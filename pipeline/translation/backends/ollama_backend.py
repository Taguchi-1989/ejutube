from __future__ import annotations

import asyncio
import os

import httpx

from .base import OllamaUnavailableError


DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma4:e4b"


class OllamaBackend:
    name = "ollama"

    def __init__(self, endpoint: str | None = None, model: str | None = None) -> None:
        self.endpoint = (endpoint or os.environ.get("OLLAMA_ENDPOINT", DEFAULT_ENDPOINT)).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)

    async def chat(
        self,
        system: str,
        user: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
    ) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            # Gemma 4 is a thinking model — without this it dumps everything
            # into message.thinking and returns empty message.content.
            "think": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        url = f"{self.endpoint}/api/chat"
        timeout = httpx.Timeout(120.0, connect=5.0)

        attempt = 0
        while True:
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                msg = data.get("message", {})
                content = (msg.get("content") or "").strip()
                if not content:
                    # Some thinking models return everything in `thinking`
                    # when think isn't honored. Use it as a fallback.
                    content = (msg.get("thinking") or "").strip()
                return content
            except httpx.ConnectError as exc:
                raise OllamaUnavailableError(
                    f"Cannot reach Ollama at {self.endpoint}. Start it with `ollama serve`. ({exc})"
                ) from exc
            except (httpx.HTTPStatusError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
                if attempt >= 1:
                    raise
                attempt += 1
                await asyncio.sleep(1.0)
