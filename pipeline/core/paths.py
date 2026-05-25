"""
Central path helpers for the pipeline.

All modules must import from here — do not define _output_dir() locally.
"""

from __future__ import annotations

import os
from pathlib import Path


def get_output_dir() -> Path:
    """Return the base output directory, honoring OUTPUT_DIR env var."""
    env = os.environ.get("OUTPUT_DIR")
    if env:
        return Path(env)
    return Path("./output")


def get_video_output_dir(video_id: str) -> Path:
    """Return the per-video output directory."""
    return get_output_dir() / video_id
