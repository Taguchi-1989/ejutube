"""
WAV duration measurement via ffprobe (primary) or wave module (fallback).
"""

from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path


def measure_wav_duration(path: Path) -> float:
    if shutil.which("ffprobe"):
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            stripped = result.stdout.strip()
            if stripped:
                return float(stripped)

    # fallback: parse WAV header
    try:
        with wave.open(str(path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate == 0:
                raise ValueError(f"Invalid framerate in {path}")
            return frames / rate
    except Exception as exc:
        raise RuntimeError(
            f"Could not determine duration of {path}: {exc}"
        ) from exc
