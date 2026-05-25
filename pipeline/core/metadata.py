"""
Video metadata init, load, and status-update helpers.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pipeline.core.paths import get_video_output_dir
from pipeline.models import Metadata, ProcessingStatus
from pipeline.core.video_id import extract_video_id


def _output_dir(video_id: str) -> Path:
    d = get_video_output_dir(video_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def init_metadata(url: str) -> Metadata:
    """
    Extract video_id from *url*, fetch title/channel/duration via yt-dlp,
    write metadata.json, and return the Metadata object.

    If yt-dlp fails (private video, age-gate, network error), fall back to
    a minimal placeholder so the pipeline can still proceed.
    """
    video_id = extract_video_id(url)
    out_dir = _output_dir(video_id)

    title, channel, duration = _fetch_yt_info(url)

    meta = Metadata(
        video_id=video_id,
        url=url,
        title=title,
        channel=channel,
        duration=duration,
        created_at=datetime.now(timezone.utc).isoformat(),
        status=ProcessingStatus.metadata_loaded,
    )
    _write(out_dir, meta)
    return meta


def load_metadata(video_id: str) -> Metadata:
    """Load and return the Metadata stored in output/{video_id}/metadata.json."""
    path = _output_dir(video_id) / "metadata.json"
    if not path.exists():
        raise FileNotFoundError(f"metadata.json not found for video_id={video_id!r}")
    return Metadata.model_validate_json(path.read_text(encoding="utf-8"))


def update_status(video_id: str, status: ProcessingStatus) -> Metadata:
    """Load, update status, re-write, and return the updated Metadata."""
    meta = load_metadata(video_id)
    meta = meta.model_copy(update={"status": status})
    _write(_output_dir(video_id), meta)
    return meta


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_yt_info(url: str) -> tuple[str, str, float]:
    """
    Run yt-dlp --dump-json to get title, channel, and duration.

    Returns (title, channel, duration_seconds).
    Falls back to placeholder values if yt-dlp is unavailable or fails.
    """
    try:
        result = subprocess.run(
            ["yt-dlp", "--skip-download", "--dump-json", "--no-playlist", url],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())

        data = json.loads(result.stdout)
        title = data.get("title") or "[unknown title]"
        channel = data.get("channel") or data.get("uploader") or "[unknown channel]"
        duration = float(data.get("duration") or 0.0)
        return title, channel, duration

    except (FileNotFoundError, subprocess.TimeoutExpired, RuntimeError, json.JSONDecodeError):
        # yt-dlp not installed, timed out, or video unavailable
        return "[placeholder title]", "[unknown channel]", 0.0


def _write(out_dir: Path, meta: Metadata) -> None:
    path = out_dir / "metadata.json"
    path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
