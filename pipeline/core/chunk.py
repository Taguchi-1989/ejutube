"""
Group normalized TranscriptItems into 10-30 second Chunks.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pipeline.models import Chunk, TranscriptItem

_SENTENCE_ENDINGS = frozenset(".?!\n")


def _output_dir(video_id: str) -> Path:
    base = Path(os.environ.get("OUTPUT_DIR", "./output"))
    return base / video_id


def chunk(
    video_id: str,
    target_seconds: int = 25,
    max_seconds: int = 30,
) -> list[Chunk]:
    """
    Read transcript.normalized.json for *video_id* and group items into
    time-bounded chunks, writing the result to chunks.json.

    Greedy algorithm: accumulate items until the running duration reaches
    *target_seconds*.  When near *target_seconds* prefer to break at a
    sentence boundary (cue text ending with . ? ! or followed by a gap).
    Hard-cap at *max_seconds* regardless of sentence boundaries.
    """
    out_dir = _output_dir(video_id)
    normalized_path = out_dir / "transcript.normalized.json"
    if not normalized_path.exists():
        raise FileNotFoundError(
            f"transcript.normalized.json not found in {out_dir}. "
            "Run 'normalize' first."
        )

    raw = json.loads(normalized_path.read_text(encoding="utf-8"))
    items = [TranscriptItem(**r) for r in raw]

    chunks = _build_chunks(items, target_seconds, max_seconds)

    out_path = out_dir / "chunks.json"
    out_path.write_text(
        json.dumps([c.model_dump(exclude_none=True) for c in chunks], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return chunks


def _is_sentence_boundary(item: TranscriptItem) -> bool:
    """True if the cue text ends with a sentence-ending punctuation mark."""
    text = item.text_en.rstrip()
    return bool(text) and text[-1] in _SENTENCE_ENDINGS


def _build_chunks(
    items: list[TranscriptItem],
    target_seconds: int,
    max_seconds: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    chunk_id = 1
    bucket: list[TranscriptItem] = []

    for item in items:
        # If adding this item would push past max_seconds, flush first.
        if bucket:
            prospective_duration = item.end - bucket[0].start
            if prospective_duration > max_seconds:
                chunks.append(_make_chunk(chunk_id, bucket))
                chunk_id += 1
                bucket = []

        bucket.append(item)
        duration = bucket[-1].end - bucket[0].start

        at_target = duration >= target_seconds
        # Hard flush at max_seconds (catches the single-item case where one
        # cue is itself longer than max_seconds).
        at_max = duration >= max_seconds

        if at_max or (at_target and _is_sentence_boundary(item)):
            chunks.append(_make_chunk(chunk_id, bucket))
            chunk_id += 1
            bucket = []

    # Flush any remaining items
    if bucket:
        # If there's a previous chunk and the remainder is very short,
        # attach it to the previous chunk to avoid tiny trailing chunks.
        # However, the schema has no min-duration rule so just emit it.
        chunks.append(_make_chunk(chunk_id, bucket))

    return chunks


def _make_chunk(chunk_id: int, items: list[TranscriptItem]) -> Chunk:
    text_en = "\n".join(item.text_en for item in items)
    return Chunk(
        chunk_id=chunk_id,
        start=items[0].start,
        end=items[-1].end,
        items=[item.id for item in items],
        text_en=text_en,
    )
