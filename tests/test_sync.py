"""
Tests for pipeline/sync — build_player_json.

Run with: pytest tests/test_sync.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

import pytest

from pipeline.models import Chunk, NarrationSegment, PlayerJson

_TMP_BASE = Path("D:/tmp/ejutube_tests")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_output():
    tmp_path = _TMP_BASE / uuid.uuid4().hex
    tmp_path.mkdir(parents=True, exist_ok=True)
    original = os.environ.get("OUTPUT_DIR")
    os.environ["OUTPUT_DIR"] = str(tmp_path)
    yield tmp_path
    shutil.rmtree(tmp_path, ignore_errors=True)
    if original is None:
        os.environ.pop("OUTPUT_DIR", None)
    else:
        os.environ["OUTPUT_DIR"] = original


def _write_chunks(vid_dir: Path, chunks: list[dict]) -> None:
    (vid_dir / "chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _write_segments(vid_dir: Path, segments: list[dict]) -> None:
    (vid_dir / "narration_segments.json").write_text(
        json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8"
    )


_SAMPLE_CHUNKS = [
    {
        "chunk_id": 1,
        "start": 0.0,
        "end": 15.0,
        "items": [1, 2],
        "text_en": "Welcome to this tutorial.",
        "subtitle_ja": "このチュートリアルへようこそ。",
        "narration_ja": "このチュートリアルへようこそ。",
    },
    {
        "chunk_id": 2,
        "start": 15.0,
        "end": 30.0,
        "items": [3, 4],
        "text_en": "Open your terminal.",
        "subtitle_ja": "ターミナルを開いてください。",
        "narration_ja": "ターミナルを開いてください。",
    },
    {
        "chunk_id": 3,
        "start": 30.0,
        "end": 45.0,
        "items": [5],
        "text_en": "Run npm install.",
        "subtitle_ja": "npm install を実行します。",
        "narration_ja": "npm install を実行します。",
    },
]

_SAMPLE_SEGMENTS = [
    {
        "chunk_id": 1,
        "video_start": 0.0,
        "video_end": 15.0,
        "target_duration": 15.0,
        "audio_duration": 14.2,
        "duration_diff": -0.8,
        "audio_file": "audio/0001.wav",
    },
    {
        "chunk_id": 2,
        "video_start": 15.0,
        "video_end": 30.0,
        "target_duration": 15.0,
        "audio_duration": 16.1,
        "duration_diff": 1.1,
        "audio_file": "audio/0002.wav",
    },
    {
        "chunk_id": 3,
        "video_start": 30.0,
        "video_end": 45.0,
        "target_duration": 15.0,
        "audio_duration": 13.5,
        "duration_diff": -1.5,
        "audio_file": "audio/0003.wav",
    },
]


# ---------------------------------------------------------------------------
# test_build_player_json_happy_path
# ---------------------------------------------------------------------------

def test_build_player_json_happy_path(tmp_output):
    video_id = "HAPYTEST0AB"
    vid_dir = tmp_output / video_id
    vid_dir.mkdir(parents=True, exist_ok=True)

    _write_chunks(vid_dir, _SAMPLE_CHUNKS)
    _write_segments(vid_dir, _SAMPLE_SEGMENTS)

    from pipeline.sync import build_player_json
    player = build_player_json(video_id)

    assert isinstance(player, PlayerJson)
    assert player.video_id == video_id
    assert player.audio_offset == 0.0
    assert len(player.chunks) == 3

    c1 = player.chunks[0]
    assert c1.chunk_id == 1
    assert c1.start == 0.0
    assert c1.end == 15.0
    assert c1.audio == "audio/0001.wav"
    assert c1.subtitle_ja == "このチュートリアルへようこそ。"
    assert c1.narration_ja == "このチュートリアルへようこそ。"
    assert c1.summary == ""

    player_path = vid_dir / "player.json"
    assert player_path.exists()
    raw = json.loads(player_path.read_text(encoding="utf-8"))
    assert raw["video_id"] == video_id
    assert len(raw["chunks"]) == 3


# ---------------------------------------------------------------------------
# test_build_player_preserves_audio_offset
# ---------------------------------------------------------------------------

def test_build_player_preserves_audio_offset(tmp_output):
    video_id = "OFFSETTEST1"
    vid_dir = tmp_output / video_id
    vid_dir.mkdir(parents=True, exist_ok=True)

    _write_chunks(vid_dir, _SAMPLE_CHUNKS)
    _write_segments(vid_dir, _SAMPLE_SEGMENTS)

    # Pre-write a player.json with a non-zero audio_offset
    existing_player = {
        "video_id": video_id,
        "audio_offset": -0.8,
        "chunks": [],
    }
    (vid_dir / "player.json").write_text(
        json.dumps(existing_player, ensure_ascii=False), encoding="utf-8"
    )

    from pipeline.sync import build_player_json
    player = build_player_json(video_id)

    assert player.audio_offset == -0.8


# ---------------------------------------------------------------------------
# test_build_player_handles_missing_narration
# ---------------------------------------------------------------------------

def test_build_player_handles_missing_narration(tmp_output):
    video_id = "NONARRTEST1"
    vid_dir = tmp_output / video_id
    vid_dir.mkdir(parents=True, exist_ok=True)

    chunks_with_empty = [
        {
            "chunk_id": 1,
            "start": 0.0,
            "end": 15.0,
            "items": [1],
            "text_en": "Hello world.",
            "subtitle_ja": "こんにちは。",
            "narration_ja": None,
        },
        {
            "chunk_id": 2,
            "start": 15.0,
            "end": 30.0,
            "items": [2],
            "text_en": "Second line.",
            "subtitle_ja": None,
            "narration_ja": None,
        },
    ]
    _write_chunks(vid_dir, chunks_with_empty)
    # No narration_segments.json — should not crash

    from pipeline.sync import build_player_json
    player = build_player_json(video_id)

    assert len(player.chunks) == 2
    assert player.chunks[0].audio == ""
    assert player.chunks[1].audio == ""
    assert player.chunks[0].subtitle_ja == "こんにちは。"
    assert player.chunks[1].subtitle_ja == ""
    assert player.chunks[0].narration_ja == ""


# ---------------------------------------------------------------------------
# test_build_player_validates_against_schema
# ---------------------------------------------------------------------------

def test_build_player_validates_against_schema(tmp_output):
    video_id = "SCHEMATEST1"
    vid_dir = tmp_output / video_id
    vid_dir.mkdir(parents=True, exist_ok=True)

    _write_chunks(vid_dir, _SAMPLE_CHUNKS)
    _write_segments(vid_dir, _SAMPLE_SEGMENTS)

    from pipeline.sync import build_player_json
    player = build_player_json(video_id)

    # Pydantic round-trip
    dumped = player.model_dump()
    reloaded = PlayerJson.model_validate(dumped)

    assert reloaded.video_id == player.video_id
    assert reloaded.audio_offset == player.audio_offset
    assert len(reloaded.chunks) == len(player.chunks)

    for orig, reloaded_chunk in zip(player.chunks, reloaded.chunks):
        assert orig.chunk_id == reloaded_chunk.chunk_id
        assert orig.start == reloaded_chunk.start
        assert orig.end == reloaded_chunk.end
        assert orig.audio == reloaded_chunk.audio
        assert orig.subtitle_ja == reloaded_chunk.subtitle_ja
        assert orig.narration_ja == reloaded_chunk.narration_ja

    # JSON round-trip from written file
    player_path = vid_dir / "player.json"
    raw = json.loads(player_path.read_text(encoding="utf-8"))
    reloaded_from_file = PlayerJson.model_validate(raw)
    assert reloaded_from_file.video_id == video_id


# ---------------------------------------------------------------------------
# test_build_player_empty_narration_no_model_construct
# ---------------------------------------------------------------------------

def test_build_player_empty_narration_no_model_construct(tmp_output):
    """
    Chunks with empty narration_ja (no TTS segment) must produce audio="" and
    validate cleanly through Pydantic — no model_construct bypass required.
    """
    video_id = "NOAUDIOTEST"
    vid_dir = tmp_output / video_id
    vid_dir.mkdir(parents=True, exist_ok=True)

    chunks_no_narration = [
        {
            "chunk_id": 1,
            "start": 0.0,
            "end": 15.0,
            "items": [1],
            "text_en": "Hello world.",
            "subtitle_ja": "こんにちは。",
            "narration_ja": None,  # no narration -> no TTS -> no audio file
        },
    ]
    _write_chunks(vid_dir, chunks_no_narration)
    # No narration_segments.json written — simulates pre-TTS state

    from pipeline.sync import build_player_json
    player = build_player_json(video_id)

    assert len(player.chunks) == 1
    chunk = player.chunks[0]
    assert chunk.audio == ""

    # Must round-trip cleanly through Pydantic without model_construct
    dumped = player.model_dump()
    reloaded = PlayerJson.model_validate(dumped)
    assert reloaded.chunks[0].audio == ""

    # JSON written to disk must also validate
    player_path = vid_dir / "player.json"
    raw = json.loads(player_path.read_text(encoding="utf-8"))
    assert raw["chunks"][0]["audio"] == ""
    reloaded_from_file = PlayerJson.model_validate(raw)
    assert reloaded_from_file.chunks[0].audio == ""
