"""
Assembles player.json from chunks.json, narration_segments.json, and summary.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from pipeline.core.paths import get_video_output_dir
from pipeline.models import Chunk, NarrationSegment, PlayerChunk, PlayerJson


def _extract_chunk_summaries(summary_path: Path) -> dict[int, str]:
    """
    Parse summary.md for per-chunk summary sections.

    Looks for headings like "## Chunk 1", "### Chunk 2", "#### チャンク 3", etc.
    Returns {chunk_id: summary_text}.
    """
    if not summary_path.exists():
        return {}

    text = summary_path.read_text(encoding="utf-8")
    summaries: dict[int, str] = {}

    pattern = re.compile(
        r"^#{1,6}\s+(?:Chunk|チャンク)\s+(\d+)\b.*$",
        re.MULTILINE | re.IGNORECASE,
    )

    matches = list(pattern.finditer(text))
    for i, match in enumerate(matches):
        chunk_id = int(match.group(1))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        # Strip sub-headings if any
        body = re.sub(r"^#{1,6}\s+.*$", "", body, flags=re.MULTILINE).strip()
        summaries[chunk_id] = body

    return summaries


def _load_existing_audio_offset(player_path: Path) -> float:
    """Return the existing audio_offset from player.json if present, else 0.0."""
    if not player_path.exists():
        return 0.0
    try:
        data = json.loads(player_path.read_text(encoding="utf-8"))
        return float(data.get("audio_offset", 0.0))
    except (json.JSONDecodeError, OSError, KeyError, ValueError):
        return 0.0


def build_player_json(video_id: str) -> PlayerJson:
    """
    Read chunks.json + narration_segments.json + summary.md and produce player.json.

    Preserves any existing audio_offset in player.json.
    """
    vid_dir = get_video_output_dir(video_id)

    chunks_path = vid_dir / "chunks.json"
    if not chunks_path.exists():
        raise FileNotFoundError(f"chunks.json not found: {chunks_path}")

    raw_chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    chunks = [Chunk.model_validate(c) for c in raw_chunks]

    segments_path = vid_dir / "narration_segments.json"
    segment_by_chunk: dict[int, NarrationSegment] = {}
    if segments_path.exists():
        raw_segs = json.loads(segments_path.read_text(encoding="utf-8"))
        for raw in raw_segs:
            seg = NarrationSegment.model_validate(raw)
            segment_by_chunk[seg.chunk_id] = seg

    summary_path = vid_dir / "summary.md"
    chunk_summaries = _extract_chunk_summaries(summary_path)

    player_path = vid_dir / "player.json"
    audio_offset = _load_existing_audio_offset(player_path)

    player_chunks: list[PlayerChunk] = []
    for chunk in chunks:
        seg = segment_by_chunk.get(chunk.chunk_id)
        audio = seg.audio_file if seg is not None else ""
        subtitle_ja = chunk.subtitle_ja or ""
        narration_ja = chunk.narration_ja or ""
        summary = chunk_summaries.get(chunk.chunk_id, "")

        player_chunk = PlayerChunk(
            chunk_id=chunk.chunk_id,
            start=chunk.start,
            end=chunk.end,
            audio=audio,
            subtitle_ja=subtitle_ja,
            narration_ja=narration_ja,
            summary=summary,
        )

        player_chunks.append(player_chunk)

    player = PlayerJson(
        video_id=video_id,
        audio_offset=audio_offset,
        chunks=player_chunks,
    )

    vid_dir.mkdir(parents=True, exist_ok=True)
    player_path.write_text(
        json.dumps(player.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return player
