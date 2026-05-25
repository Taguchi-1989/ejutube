"""
Pydantic v2 models corresponding 1:1 to schemas/*.schema.json.

Downstream agents must import from this module — do not define duplicate models.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Status enum — mirrors metadata.schema.json "status" enum
# ---------------------------------------------------------------------------

class ProcessingStatus(str, Enum):
    """Pipeline processing states (section 10.1 + 10.2)."""

    created = "created"
    metadata_loaded = "metadata_loaded"
    subtitle_fetched = "subtitle_fetched"
    subtitle_normalized = "subtitle_normalized"
    chunked = "chunked"
    translated = "translated"
    narration_script_created = "narration_script_created"
    tts_generated = "tts_generated"
    sync_generated = "sync_generated"
    completed = "completed"
    failed_no_subtitle = "failed_no_subtitle"
    failed_translation = "failed_translation"
    failed_tts = "failed_tts"
    failed_sync = "failed_sync"
    failed_unknown = "failed_unknown"


# ---------------------------------------------------------------------------
# metadata.schema.json
# ---------------------------------------------------------------------------

class Metadata(BaseModel):
    """
    Per-video metadata written to output/{video_id}/metadata.json.

    Pattern constraints match the JSON schema exactly.
    """

    model_config = ConfigDict(populate_by_name=True)

    video_id: str = Field(
        ...,
        pattern=r"^[A-Za-z0-9_-]{11}$",
        description="YouTube video_id (11-char alphanumeric)",
    )
    url: str = Field(..., description="Original YouTube URL")
    title: str = Field(..., min_length=1, description="Video title")
    channel: str = Field(..., min_length=1, description="Channel name")
    duration: float = Field(..., ge=0, description="Total duration in seconds")
    created_at: str = Field(
        ...,
        description="Record creation datetime (ISO 8601)",
    )
    status: ProcessingStatus = Field(
        default=ProcessingStatus.created,
        description="Current pipeline status",
    )


# ---------------------------------------------------------------------------
# transcript-normalized.schema.json
# ---------------------------------------------------------------------------

class TranscriptItem(BaseModel):
    """One normalized subtitle cue (section 8.4)."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(..., ge=1, description="1-based sequential id")
    start: float = Field(..., ge=0, description="Cue start time in seconds")
    end: float = Field(..., ge=0, description="Cue end time in seconds")
    text_en: str = Field(..., min_length=1, description="English subtitle text")


# ---------------------------------------------------------------------------
# chunks.schema.json
# ---------------------------------------------------------------------------

class Chunk(BaseModel):
    """
    10-30 second processing unit (section 8.5 / 9.3).

    subtitle_ja and narration_ja are absent until the translation step runs.
    """

    model_config = ConfigDict(populate_by_name=True)

    chunk_id: int = Field(..., ge=1, description="1-based sequential id")
    start: float = Field(..., ge=0, description="Chunk start time in seconds")
    end: float = Field(..., ge=0, description="Chunk end time in seconds")
    items: list[int] = Field(
        default_factory=list,
        description="TranscriptItem ids included in this chunk",
    )
    text_en: str = Field(..., min_length=1, description="Combined English text")
    subtitle_ja: Optional[str] = Field(
        default=None, description="Japanese subtitle (set after translation)"
    )
    narration_ja: Optional[str] = Field(
        default=None, description="Narration script (set after narration step)"
    )


# ---------------------------------------------------------------------------
# narration-segments.schema.json
# ---------------------------------------------------------------------------

class NarrationSegment(BaseModel):
    """
    Per-chunk audio duration measurement (section 8.10).

    Written to output/{video_id}/narration_segments.json after TTS generation.
    """

    model_config = ConfigDict(populate_by_name=True)

    chunk_id: int = Field(..., ge=1, description="Corresponding chunk_id")
    video_start: float = Field(..., ge=0, description="Chunk start in video (seconds)")
    video_end: float = Field(..., ge=0, description="Chunk end in video (seconds)")
    target_duration: float = Field(
        ..., ge=0, description="video_end - video_start (seconds)"
    )
    audio_duration: float = Field(
        ..., ge=0, description="Actual TTS audio length (seconds)"
    )
    duration_diff: float = Field(
        ..., description="audio_duration - target_duration (positive = audio longer)"
    )
    audio_file: str = Field(
        ...,
        pattern=r"^audio/[0-9]{4}\.wav$",
        description="Relative path from output/{video_id}/ e.g. audio/0001.wav",
    )


# ---------------------------------------------------------------------------
# player.schema.json
# ---------------------------------------------------------------------------

class PlayerChunk(BaseModel):
    """One chunk entry inside player.json (section 9.4)."""

    model_config = ConfigDict(populate_by_name=True)

    chunk_id: int = Field(..., ge=1)
    start: float = Field(..., ge=0)
    end: float = Field(..., ge=0)
    audio: str = Field(
        default="",
        pattern=r"^(audio/[0-9]{4}\.wav)?$",
        description="Relative path from output/{video_id}/; empty string when no TTS audio exists",
    )
    subtitle_ja: str = Field(default="", description="Japanese subtitle")
    narration_ja: str = Field(default="", description="Narration script")
    summary: str = Field(default="", description="Chunk summary")


class PlayerJson(BaseModel):
    """
    Root object of player.json — loaded by the Next.js frontend (section 9.4).
    """

    model_config = ConfigDict(populate_by_name=True)

    video_id: str = Field(
        ...,
        pattern=r"^[A-Za-z0-9_-]{11}$",
    )
    audio_offset: float = Field(
        default=0.0,
        description="Global sync offset in seconds (positive = delay audio)",
    )
    chunks: list[PlayerChunk] = Field(..., min_length=1)
