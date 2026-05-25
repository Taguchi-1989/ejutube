"""
Subtitle fetch and import utilities.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from pipeline.core.paths import get_video_output_dir


class NoSubtitleError(Exception):
    """Raised when no English subtitle can be located for a video."""


def _output_dir(video_id: str) -> Path:
    d = get_video_output_dir(video_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch_subtitle(video_id: str) -> Path:
    """
    Obtain an English subtitle file for *video_id*.

    Attempt order:
      1. youtube-transcript-api (manual captions first, then auto-generated)
      2. Existing file at output/{video_id}/transcript.en.vtt
      3. Existing file at output/{video_id}/transcript.en.srt

    Returns the Path to the saved VTT file.
    Raises NoSubtitleError if nothing is found.
    """
    out_dir = _output_dir(video_id)
    vtt_path = out_dir / "transcript.en.vtt"

    # Try youtube-transcript-api
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
            YouTubeRequestFailed,
        )

        try:
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)

            # Prefer manually created EN captions; fall back to auto-generated
            try:
                transcript = transcript_list.find_manually_created_transcript(["en"])
            except NoTranscriptFound:
                transcript = transcript_list.find_generated_transcript(["en"])

            fetched = transcript.fetch()
            # FetchedTranscript is iterable; each element is a FetchedTranscriptSnippet
            cues = [
                {"start": s.start, "duration": s.duration, "text": s.text}
                for s in fetched
            ]
            _write_vtt(vtt_path, cues)
            return vtt_path

        except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable, YouTubeRequestFailed):
            # Known retrieval failures — fall through to local file fallback.
            pass

    except ImportError:
        pass  # youtube-transcript-api not installed; try local files

    # Fallback: look for a file already placed by the user
    if vtt_path.exists():
        return vtt_path

    srt_path = out_dir / "transcript.en.srt"
    if srt_path.exists():
        return srt_path

    raise NoSubtitleError(
        f"No English subtitle found for video_id={video_id!r}. "
        "Use 'fetch-subtitle --file <path>' to supply one manually."
    )


def import_local_subtitle(video_id: str, src: Path) -> Path:
    """
    Copy a user-supplied VTT or SRT file into output/{video_id}/.

    The destination filename is preserved as-is (transcript.en.vtt or
    transcript.en.srt depending on the source suffix).
    Returns the destination path.
    """
    out_dir = _output_dir(video_id)
    suffix = src.suffix.lower()
    if suffix == ".vtt":
        dest = out_dir / "transcript.en.vtt"
    elif suffix == ".srt":
        dest = out_dir / "transcript.en.srt"
    else:
        raise ValueError(f"Unsupported subtitle format: {src.suffix!r} (expected .vtt or .srt)")

    shutil.copy2(src, dest)
    return dest


def _write_vtt(path: Path, cues: list) -> None:
    """
    Serialize transcript-api cue dicts to a minimal VTT file.

    Each cue dict has at minimum: 'start' (float seconds), 'duration' (float), 'text' (str).
    """
    lines = ["WEBVTT", ""]
    for cue in cues:
        start = cue["start"]
        end = start + cue["duration"]
        lines.append(f"{_fmt_ts(start)} --> {_fmt_ts(end)}")
        lines.append(cue["text"].replace("\n", " "))
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def _fmt_ts(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm for VTT."""
    ms = round(seconds * 1000)
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1_000
    ms %= 1_000
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
