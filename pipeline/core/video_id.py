"""
Extract and validate YouTube video IDs from various URL formats.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(url: str) -> str:
    """
    Parse a YouTube URL and return the 11-character video ID.

    Handles:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - https://www.youtube.com/shorts/VIDEO_ID
      - https://www.youtube.com/embed/VIDEO_ID
      - bare VIDEO_ID (11-char alphanumeric)

    Raises ValueError if the input cannot be resolved to a valid video ID.
    """
    stripped = url.strip()

    # Accept bare video IDs directly
    if _VIDEO_ID_RE.match(stripped):
        return stripped

    parsed = urlparse(stripped)

    host = parsed.netloc.lower().lstrip("www.")
    path = parsed.path

    if host in ("youtube.com", "m.youtube.com"):
        # /watch?v=...
        if path == "/watch":
            qs = parse_qs(parsed.query)
            ids = qs.get("v", [])
            if ids:
                return _validate(ids[0])

        # /shorts/VIDEO_ID  or  /embed/VIDEO_ID
        m = re.match(r"^/(?:shorts|embed)/([^/?&]+)", path)
        if m:
            return _validate(m.group(1))

    elif host == "youtu.be":
        # /VIDEO_ID
        candidate = path.lstrip("/").split("/")[0].split("?")[0]
        if candidate:
            return _validate(candidate)

    raise ValueError(f"Cannot extract a valid YouTube video ID from: {url!r}")


def _validate(candidate: str) -> str:
    if not _VIDEO_ID_RE.match(candidate):
        raise ValueError(
            f"Extracted string {candidate!r} is not a valid YouTube video ID "
            "(must be exactly 11 alphanumeric/dash/underscore characters)"
        )
    return candidate
