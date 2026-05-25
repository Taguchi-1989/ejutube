"""
Tests for pipeline/tts/presets.py and preset integration with synthesize_all.
"""

from __future__ import annotations

import io
import json
import wave
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from pipeline.tts.presets import (
    DEFAULT_PRESET,
    PRESETS,
    SpeakerPreset,
    get_default,
    get_preset,
    list_presets,
)


# ---------------------------------------------------------------------------
# get_default
# ---------------------------------------------------------------------------

class TestGetDefault:
    def test_returns_tsumugi(self):
        preset = get_default()
        assert preset.name == "tsumugi"
        assert preset.display_name == "春日部つむぎ"
        assert preset.speaker_id == 8
        assert preset.style == "ノーマル"

    def test_default_preset_key_is_tsumugi(self):
        assert DEFAULT_PRESET == "tsumugi"


# ---------------------------------------------------------------------------
# get_preset
# ---------------------------------------------------------------------------

class TestGetPreset:
    def test_tsumugi(self):
        preset = get_preset("tsumugi")
        assert isinstance(preset, SpeakerPreset)
        assert preset.speaker_id == 8
        assert preset.display_name == "春日部つむぎ"

    def test_zundamon(self):
        # Verified against VOICEVOX v0.25.0 /speakers
        preset = get_preset("zundamon")
        assert preset.speaker_id == 3
        assert preset.display_name == "ずんだもん"

    def test_metan(self):
        preset = get_preset("metan")
        assert preset.speaker_id == 2
        assert preset.display_name == "四国めたん"

    def test_nonexistent_raises_key_error(self):
        with pytest.raises(KeyError, match="nonexistent"):
            get_preset("nonexistent")

    def test_error_message_lists_valid_keys(self):
        with pytest.raises(KeyError) as exc_info:
            get_preset("bad_key")
        msg = str(exc_info.value)
        assert "tsumugi" in msg or "zundamon" in msg


# ---------------------------------------------------------------------------
# list_presets
# ---------------------------------------------------------------------------

class TestListPresets:
    def test_returns_three_entries(self):
        presets = list_presets()
        assert len(presets) == 3

    def test_all_are_speaker_presets(self):
        for preset in list_presets():
            assert isinstance(preset, SpeakerPreset)

    def test_contains_all_keys(self):
        names = {p.name for p in list_presets()}
        assert names == {"tsumugi", "zundamon", "metan"}


# ---------------------------------------------------------------------------
# synthesize_all with preset_name
# ---------------------------------------------------------------------------

def _make_chunks_json(tmp_path: Path, video_id: str) -> Path:
    video_dir = tmp_path / "output" / video_id
    video_dir.mkdir(parents=True)
    chunks = [
        {
            "chunk_id": 1,
            "start": 0.0,
            "end": 15.0,
            "items": [1],
            "text_en": "Hello world.",
            "subtitle_ja": "こんにちは世界。",
            "narration_ja": "こんにちは、世界。",
        },
    ]
    path = video_dir / "chunks.json"
    path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    return path


def _fake_wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(b"\x00\x00" * 24000)
    return buf.getvalue()


class TestSynthesizeAllWithPreset:
    def test_preset_name_tsumugi_uses_speaker_id_8(self, tmp_path, monkeypatch):
        video_id = "PRESET_TEST_001"
        _make_chunks_json(tmp_path, video_id)
        monkeypatch.chdir(tmp_path)

        fake_wav = _fake_wav_bytes()
        captured_speaker_ids: list[int] = []

        async def fake_audio_query(text, speaker, **kwargs):
            captured_speaker_ids.append(speaker)
            return {"speedScale": 1.1, "volumeScale": 1.0}

        async def fake_synthesize(query, speaker):
            return fake_wav

        with patch("pipeline.tts.synthesize.VoicevoxClient") as MockClient:
            instance = AsyncMock()
            instance.audio_query = AsyncMock(side_effect=fake_audio_query)
            instance.synthesize = AsyncMock(side_effect=fake_synthesize)
            MockClient.return_value = instance

            from pipeline.tts.synthesize import synthesize_all
            synthesize_all(video_id=video_id, preset_name="tsumugi", force=True)

        assert captured_speaker_ids == [8]

    def test_explicit_speaker_overrides_preset(self, tmp_path, monkeypatch):
        video_id = "PRESET_TEST_002"
        _make_chunks_json(tmp_path, video_id)
        monkeypatch.chdir(tmp_path)

        fake_wav = _fake_wav_bytes()
        captured_speaker_ids: list[int] = []

        async def fake_audio_query(text, speaker, **kwargs):
            captured_speaker_ids.append(speaker)
            return {"speedScale": 1.1, "volumeScale": 1.0}

        async def fake_synthesize(query, speaker):
            return fake_wav

        with patch("pipeline.tts.synthesize.VoicevoxClient") as MockClient:
            instance = AsyncMock()
            instance.audio_query = AsyncMock(side_effect=fake_audio_query)
            instance.synthesize = AsyncMock(side_effect=fake_synthesize)
            MockClient.return_value = instance

            from pipeline.tts.synthesize import synthesize_all
            # speaker=99 should win over preset_name="tsumugi" (id=8)
            synthesize_all(
                video_id=video_id,
                speaker=99,
                preset_name="tsumugi",
                force=True,
            )

        assert captured_speaker_ids == [99]

    def test_default_preset_used_when_no_args(self, tmp_path, monkeypatch):
        video_id = "PRESET_TEST_003"
        _make_chunks_json(tmp_path, video_id)
        monkeypatch.chdir(tmp_path)

        fake_wav = _fake_wav_bytes()
        captured_speaker_ids: list[int] = []

        async def fake_audio_query(text, speaker, **kwargs):
            captured_speaker_ids.append(speaker)
            return {"speedScale": 1.1, "volumeScale": 1.0}

        async def fake_synthesize(query, speaker):
            return fake_wav

        with patch("pipeline.tts.synthesize.VoicevoxClient") as MockClient:
            instance = AsyncMock()
            instance.audio_query = AsyncMock(side_effect=fake_audio_query)
            instance.synthesize = AsyncMock(side_effect=fake_synthesize)
            MockClient.return_value = instance

            from pipeline.tts.synthesize import synthesize_all
            # No speaker, no preset_name -> uses default (tsumugi, id=8)
            synthesize_all(video_id=video_id, force=True)

        assert captured_speaker_ids == [8]
