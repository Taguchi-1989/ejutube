"""
Normalize VTT/SRT subtitle files into TranscriptItem lists.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pipeline.models import TranscriptItem

_NOISE_RE = re.compile(
    r"<[^>]+>"             # HTML/WebVTT tags like <c.color>, <b>, etc.
    r"|&[a-z]+;"           # HTML entities
    r"|\[♪[^\]]*\]"        # Music markers [♪...]
    r"|♪[^♪]*♪?"           # Bare music notes
    r"|>>\s*"              # Speaker prefix >>
    r"|\[.*?\]"            # Any [bracketed] content (applause, music, etc.)
    r"|\(.*?\)"            # Any (parenthesised) content
)

_MERGE_GAP_S = 0.3   # merge consecutive cues whose gap is less than this
_SPLIT_LONG_S = 8.0  # split single cues longer than this
_MIN_DURATION_S = 1.0  # merge cues shorter than this with the next cue


def _output_dir(video_id: str) -> Path:
    base = Path(os.environ.get("OUTPUT_DIR", "./output"))
    return base / video_id


def normalize(video_id: str) -> list[TranscriptItem]:
    """
    Read transcript.en.vtt (or .srt) for *video_id* and produce a clean
    TranscriptItem list, writing it to transcript.normalized.json.
    """
    out_dir = _output_dir(video_id)
    vtt_path = out_dir / "transcript.en.vtt"
    srt_path = out_dir / "transcript.en.srt"

    if vtt_path.exists():
        cues = _parse_vtt(vtt_path)
    elif srt_path.exists():
        cues = _parse_srt(srt_path)
    else:
        raise FileNotFoundError(
            f"No subtitle file found in {out_dir}. "
            "Run 'fetch-subtitle' first."
        )

    cleaned = _clean_cues(cues)
    items = _build_items(cleaned)

    out_path = out_dir / "transcript.normalized.json"
    out_path.write_text(
        json.dumps([item.model_dump() for item in items], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return items


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _ts_to_seconds(ts: str) -> float:
    """Convert HH:MM:SS.mmm or MM:SS.mmm to float seconds."""
    ts = ts.strip()
    parts = ts.replace(",", ".").split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(parts[0])


def _parse_vtt(path: Path) -> list[dict]:
    """Parse a VTT file using webvtt-py, returning raw cue dicts."""
    import webvtt

    cues = []
    for cue in webvtt.read(str(path)):
        cues.append({
            "start": _ts_to_seconds(cue.start),
            "end": _ts_to_seconds(cue.end),
            "text": cue.text,
        })
    return cues


def _parse_srt(path: Path) -> list[dict]:
    """Parse an SRT file using pysubs2, returning raw cue dicts."""
    import pysubs2

    subs = pysubs2.load(str(path), encoding="utf-8")
    cues = []
    for event in subs:
        if event.type != "Dialogue":
            continue
        cues.append({
            "start": event.start / 1000.0,
            "end": event.end / 1000.0,
            "text": event.plaintext,
        })
    return cues


# ---------------------------------------------------------------------------
# Cleaning pipeline
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    text = _NOISE_RE.sub("", text)
    # Collapse internal whitespace/newlines
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_cues(raw: list[dict]) -> list[dict]:
    """Remove noise, drop empties/duplicates, normalize whitespace."""
    seen_texts: set[str] = set()
    result = []
    for cue in raw:
        text = _clean_text(cue["text"])
        if not text:
            continue
        # Drop exact-text duplicates at the same timestamp
        key = (round(cue["start"], 2), text)
        if key in seen_texts:
            continue
        seen_texts.add(key)
        result.append({"start": cue["start"], "end": cue["end"], "text": text})
    return result


def _build_items(cues: list[dict]) -> list[TranscriptItem]:
    """Merge short cues, split long cues, assign sequential ids."""
    # Step 1: merge cues where gap < _MERGE_GAP_S and duration < _MIN_DURATION_S
    merged = _merge_short(cues)
    # Step 2: split cues longer than _SPLIT_LONG_S
    split = _split_long(merged)
    # Step 3: assign ids and validate
    items = []
    for i, cue in enumerate(split, start=1):
        items.append(
            TranscriptItem(
                id=i,
                start=round(cue["start"], 3),
                end=round(cue["end"], 3),
                text_en=cue["text"],
            )
        )
    return items


def _merge_short(cues: list[dict]) -> list[dict]:
    """
    Merge consecutive cues when:
      - The cue duration is < _MIN_DURATION_S, AND
      - The gap to the next cue is < _MERGE_GAP_S
    """
    if not cues:
        return []

    result = [dict(cues[0])]
    for curr in cues[1:]:
        prev = result[-1]
        gap = curr["start"] - prev["end"]
        duration = prev["end"] - prev["start"]
        if duration < _MIN_DURATION_S and gap < _MERGE_GAP_S:
            # Merge: extend prev to cover curr
            prev["end"] = curr["end"]
            prev["text"] = prev["text"] + " " + curr["text"]
        else:
            result.append(dict(curr))
    return result


def _split_long(cues: list[dict]) -> list[dict]:
    """Split any cue whose duration exceeds _SPLIT_LONG_S into two halves."""
    result = []
    for cue in cues:
        duration = cue["end"] - cue["start"]
        if duration > _SPLIT_LONG_S:
            mid_time = cue["start"] + duration / 2
            words = cue["text"].split()
            mid_word = len(words) // 2
            first_text = " ".join(words[:mid_word]).strip()
            second_text = " ".join(words[mid_word:]).strip()
            if first_text:
                result.append({"start": cue["start"], "end": mid_time, "text": first_text})
            if second_text:
                result.append({"start": mid_time, "end": cue["end"], "text": second_text})
        else:
            result.append(cue)
    return result
