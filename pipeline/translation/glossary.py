"""Glossary loading for translation prompts (section 8.8)."""

from __future__ import annotations

import json
import os
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _REPO_ROOT / "glossary.default.json"


def _output_dir(video_id: str) -> Path:
    base = Path(os.environ.get("OUTPUT_DIR", _REPO_ROOT / "output"))
    return base / video_id


def load_glossary(path: Path | None = None) -> dict[str, str]:
    """Load the default glossary, optionally merged with per-video override."""
    data: dict[str, str] = {}
    src = path if path is not None else _DEFAULT_PATH
    if src.exists():
        raw = json.loads(src.read_text(encoding="utf-8"))
        for k, v in raw.items():
            if k.startswith("_") or not isinstance(v, str):
                continue
            data[k] = v
    return data


def load_video_glossary(video_id: str) -> dict[str, str]:
    """Default glossary merged with output/{video_id}/glossary.json if present."""
    glossary = load_glossary()
    override = _output_dir(video_id) / "glossary.json"
    if override.exists():
        glossary.update(load_glossary(override))
    return glossary


def apply_glossary(text: str, glossary: dict[str, str]) -> str:
    """Return text unchanged — glossary is injected into the prompt, not substituted.

    Kept as part of the public surface so callers have a single entry point;
    regex substitution on natural language is lossy and damages morphology.
    """
    return text
