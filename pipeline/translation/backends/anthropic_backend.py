from __future__ import annotations

import asyncio
import os
from typing import Optional

from anthropic import AsyncAnthropic, RateLimitError


DEFAULT_MODEL = "claude-sonnet-4-6"

_client: Optional[AsyncAnthropic] = None


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in."
            )
        _client = AsyncAnthropic(api_key=api_key)
    return _client


def reset_client() -> None:
    global _client
    _client = None


class AnthropicBackend:
    name = "anthropic"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)

    async def chat(
        self,
        system: str,
        user: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
    ) -> str:
        client = get_client()
        system_blocks = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]
        attempt = 0
        while True:
            try:
                resp = await client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_blocks,
                    messages=[{"role": "user", "content": user}],
                )
                break
            except RateLimitError:
                if attempt >= 1:
                    raise
                attempt += 1
                await asyncio.sleep(2.0 * attempt)

        parts: list[str] = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "".join(parts).strip()
