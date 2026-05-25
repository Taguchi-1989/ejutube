"""Thin backend selector. Backwards-compatible exports for tests/callers."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from .backends import get_backend
from .backends.anthropic_backend import (
    get_client,
    reset_client,
)


def get_active_backend():
    return get_backend()


async def call_with_cache(
    system_blocks: list[dict[str, Any]],
    user: str,
    model: str,
    max_tokens: int,
    temperature: float = 0.2,
) -> str:
    """Legacy entrypoint preserved for tests and callers that still pass system_blocks.

    Routes through the Anthropic backend's underlying client so existing test
    mocks (which patch get_client) continue to work. New code should call
    backend.chat(system=..., user=...) directly.
    """
    client = get_client()
    attempt = 0
    while True:
        try:
            resp = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_blocks,
                messages=[{"role": "user", "content": user}],
            )
            break
        except Exception as exc:  # noqa: BLE001
            from anthropic import RateLimitError
            if isinstance(exc, RateLimitError) and attempt < 1:
                attempt += 1
                await asyncio.sleep(2.0 * attempt)
                continue
            raise

    parts: list[str] = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


__all__ = ["get_client", "reset_client", "call_with_cache", "get_active_backend"]
