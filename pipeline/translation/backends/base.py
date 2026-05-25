from __future__ import annotations

from typing import Protocol


class LLMBackend(Protocol):
    name: str

    async def chat(
        self,
        system: str,
        user: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
    ) -> str: ...


class OllamaUnavailableError(RuntimeError):
    pass
