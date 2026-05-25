"""
Quality checks for narration segments: flag chunks whose audio is too long.
"""

from __future__ import annotations

from pipeline.models import NarrationSegment


def flag_long_narrations(
    segments: list[NarrationSegment],
    slack_seconds: float = 3.0,
) -> list[int]:
    return [s.chunk_id for s in segments if s.duration_diff > slack_seconds]


def print_quality_warnings(segments: list[NarrationSegment], slack_seconds: float = 3.0) -> None:
    flagged = flag_long_narrations(segments, slack_seconds)
    if flagged:
        print(
            f"Warning: {len(flagged)} chunk(s) exceed target by >{slack_seconds}s "
            f"(chunk_ids: {flagged}) — consider speeding up or shortening narration."
        )
