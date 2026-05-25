"""
VOICEVOX Engine HTTP client.

Reads VOICEVOX_ENDPOINT from the environment (default http://127.0.0.1:50021).
All network I/O is async via httpx.AsyncClient.
"""

from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

_DEFAULT_ENDPOINT = "http://127.0.0.1:50021"
_TIMEOUT = 300.0


class VoicevoxUnavailableError(RuntimeError):
    pass


class VoicevoxClient:
    def __init__(self, endpoint: str | None = None) -> None:
        self._endpoint = (endpoint or os.getenv("VOICEVOX_ENDPOINT") or _DEFAULT_ENDPOINT).rstrip("/")

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{self._endpoint}/version")
                resp.raise_for_status()
                return True
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.HTTPStatusError):
            return False

    async def list_speakers(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                resp = await client.get(f"{self._endpoint}/speakers")
                resp.raise_for_status()
                return resp.json()
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                raise VoicevoxUnavailableError(
                    "Start VOICEVOX Engine — see docs/VOICEVOX_SETUP.md"
                ) from exc

    async def audio_query(
        self,
        text: str,
        speaker: int,
        speed_scale: float = 1.1,
        volume_scale: float = 1.0,
        pre_phoneme_length: float = 0.1,
        post_phoneme_length: float = 0.1,
    ) -> dict:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                resp = await client.post(
                    f"{self._endpoint}/audio_query",
                    params={"text": text, "speaker": speaker},
                )
                resp.raise_for_status()
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                raise VoicevoxUnavailableError(
                    "Start VOICEVOX Engine — see docs/VOICEVOX_SETUP.md"
                ) from exc

        query = resp.json()
        query["speedScale"] = speed_scale
        query["volumeScale"] = volume_scale
        query["prePhonemeLength"] = pre_phoneme_length
        query["postPhonemeLength"] = post_phoneme_length
        return query

    async def synthesize(self, query: dict, speaker: int) -> bytes:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                resp = await client.post(
                    f"{self._endpoint}/synthesis",
                    params={"speaker": speaker},
                    json=query,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                raise VoicevoxUnavailableError(
                    "Start VOICEVOX Engine — see docs/VOICEVOX_SETUP.md"
                ) from exc
        return resp.content
