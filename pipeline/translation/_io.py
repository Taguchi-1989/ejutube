"""Shared IO helpers for translation/narration steps."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.core.paths import get_video_output_dir
from pipeline.models import Chunk


def output_dir(video_id: str) -> Path:
    return get_video_output_dir(video_id)


def chunks_path(video_id: str) -> Path:
    return output_dir(video_id) / "chunks.json"


def load_chunks(video_id: str) -> list[Chunk]:
    path = chunks_path(video_id)
    if not path.exists():
        raise FileNotFoundError(f"chunks.json not found at {path}. Run `yt-ja chunk` first.")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Chunk.model_validate(item) for item in raw]


def save_chunks(video_id: str, chunks: list[Chunk]) -> None:
    path = chunks_path(video_id)
    payload = [c.model_dump(exclude_none=True) for c in chunks]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
