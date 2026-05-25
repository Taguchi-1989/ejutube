"""
Tests for pipeline/tts — VoicevoxClient, duration, synthesize_all, quality.
"""

from __future__ import annotations

import asyncio
import json
import wave
import struct
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pipeline.models import NarrationSegment
from pipeline.tts.quality import flag_long_narrations, print_quality_warnings
from pipeline.tts.voicevox import VoicevoxClient, VoicevoxUnavailableError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav(path: Path, duration_seconds: float = 1.0, sample_rate: int = 24000) -> Path:
    """Write a minimal silent WAV file of the given duration."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)
    return path


def _make_segment(chunk_id: int, target: float, audio: float) -> NarrationSegment:
    return NarrationSegment(
        chunk_id=chunk_id,
        video_start=0.0,
        video_end=target,
        target_duration=target,
        audio_duration=audio,
        duration_diff=audio - target,
        audio_file=f"audio/{chunk_id:04d}.wav",
    )


# ---------------------------------------------------------------------------
# VoicevoxClient — happy path
# ---------------------------------------------------------------------------

class TestVoicevoxClientHappyPath:
    @pytest.fixture
    def client(self):
        return VoicevoxClient(endpoint="http://127.0.0.1:50021")

    @pytest.mark.asyncio
    async def test_audio_query_returns_dict(self, client):
        fake_query = {
            "accent_phrases": [],
            "speedScale": 1.0,
            "volumeScale": 1.0,
            "prePhonemeLength": 0.1,
            "postPhonemeLength": 0.1,
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=fake_query.copy())

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_resp)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("pipeline.tts.voicevox.httpx.AsyncClient", return_value=mock_client_instance):
            result = await client.audio_query(text="こんにちは", speaker=3, speed_scale=1.1)

        assert result["speedScale"] == 1.1
        assert result["volumeScale"] == 1.0

    @pytest.mark.asyncio
    async def test_synthesize_returns_bytes(self, client):
        fake_wav = b"RIFF\x00\x00\x00\x00WAVEfmt "
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.content = fake_wav

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_resp)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("pipeline.tts.voicevox.httpx.AsyncClient", return_value=mock_client_instance):
            result = await client.synthesize(query={"speedScale": 1.1}, speaker=3)

        assert result == fake_wav

    @pytest.mark.asyncio
    async def test_list_speakers_returns_list(self, client):
        fake_speakers = [{"name": "ずんだもん", "styles": [{"name": "ノーマル", "id": 3}]}]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=fake_speakers)

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_resp)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("pipeline.tts.voicevox.httpx.AsyncClient", return_value=mock_client_instance):
            result = await client.list_speakers()

        assert result == fake_speakers


# ---------------------------------------------------------------------------
# VoicevoxClient — connection refused raises VoicevoxUnavailableError
# ---------------------------------------------------------------------------

class TestVoicevoxClientUnavailable:
    @pytest.fixture
    def client(self):
        return VoicevoxClient(endpoint="http://127.0.0.1:50021")

    @pytest.mark.asyncio
    async def test_audio_query_connection_refused(self, client):
        import httpx
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("pipeline.tts.voicevox.httpx.AsyncClient", return_value=mock_client_instance):
            with pytest.raises(VoicevoxUnavailableError) as exc_info:
                await client.audio_query(text="test", speaker=3)

        assert "VOICEVOX_SETUP.md" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_synthesize_connection_refused(self, client):
        import httpx
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("pipeline.tts.voicevox.httpx.AsyncClient", return_value=mock_client_instance):
            with pytest.raises(VoicevoxUnavailableError):
                await client.synthesize(query={}, speaker=3)

    @pytest.mark.asyncio
    async def test_list_speakers_connection_refused(self, client):
        import httpx
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("pipeline.tts.voicevox.httpx.AsyncClient", return_value=mock_client_instance):
            with pytest.raises(VoicevoxUnavailableError):
                await client.list_speakers()

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_refused(self, client):
        import httpx
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("pipeline.tts.voicevox.httpx.AsyncClient", return_value=mock_client_instance):
            result = await client.health_check()

        assert result is False


# ---------------------------------------------------------------------------
# measure_wav_duration — real WAV fixture
# ---------------------------------------------------------------------------

class TestMeasureWavDuration:
    def test_one_second_wav(self, tmp_path):
        from pipeline.tts.duration import measure_wav_duration

        wav = _make_wav(tmp_path / "test.wav", duration_seconds=1.0, sample_rate=24000)
        duration = measure_wav_duration(wav)
        assert abs(duration - 1.0) < 0.01

    def test_two_second_wav(self, tmp_path):
        from pipeline.tts.duration import measure_wav_duration

        wav = _make_wav(tmp_path / "test2.wav", duration_seconds=2.0, sample_rate=16000)
        duration = measure_wav_duration(wav)
        assert abs(duration - 2.0) < 0.01

    def test_missing_file_raises(self, tmp_path):
        from pipeline.tts.duration import measure_wav_duration

        with pytest.raises((RuntimeError, Exception)):
            measure_wav_duration(tmp_path / "nonexistent.wav")


# ---------------------------------------------------------------------------
# flag_long_narrations — boundary test
# ---------------------------------------------------------------------------

class TestFlagLongNarrations:
    def test_exactly_3s_diff_does_not_flag(self):
        seg = _make_segment(chunk_id=1, target=10.0, audio=13.0)
        assert seg.duration_diff == 3.0
        flagged = flag_long_narrations([seg], slack_seconds=3.0)
        assert flagged == []

    def test_3_1s_diff_flags(self):
        seg = _make_segment(chunk_id=2, target=10.0, audio=13.1)
        assert abs(seg.duration_diff - 3.1) < 0.001
        flagged = flag_long_narrations([seg], slack_seconds=3.0)
        assert flagged == [2]

    def test_negative_diff_does_not_flag(self):
        seg = _make_segment(chunk_id=3, target=20.0, audio=15.0)
        flagged = flag_long_narrations([seg], slack_seconds=3.0)
        assert flagged == []

    def test_multiple_mixed(self):
        segs = [
            _make_segment(1, 10.0, 13.0),   # diff=3.0 -> no flag
            _make_segment(2, 10.0, 13.1),   # diff=3.1 -> flag
            _make_segment(3, 10.0, 20.0),   # diff=10.0 -> flag
            _make_segment(4, 10.0, 11.0),   # diff=1.0 -> no flag
        ]
        flagged = flag_long_narrations(segs, slack_seconds=3.0)
        assert flagged == [2, 3]

    def test_empty_segments(self):
        assert flag_long_narrations([], slack_seconds=3.0) == []


# ---------------------------------------------------------------------------
# synthesize_all — mock VOICEVOX end-to-end
# ---------------------------------------------------------------------------

class TestSynthesizeAll:
    def _make_chunks_json(self, tmp_path: Path, video_id: str) -> Path:
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
            {
                "chunk_id": 2,
                "start": 15.0,
                "end": 30.0,
                "items": [2],
                "text_en": "Second chunk.",
                "subtitle_ja": "二番目のチャンク。",
                "narration_ja": "次のチャンクです。",
            },
            {
                "chunk_id": 3,
                "start": 30.0,
                "end": 45.0,
                "items": [3],
                "text_en": "No narration.",
                "subtitle_ja": None,
                "narration_ja": None,  # should be skipped
            },
        ]
        path = video_dir / "chunks.json"
        path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
        return path

    def test_synthesize_all_writes_wav_and_segments(self, tmp_path, monkeypatch):
        video_id = "DEMO0000001"
        self._make_chunks_json(tmp_path, video_id)

        # Redirect output to tmp_path
        monkeypatch.chdir(tmp_path)

        # Build a real 1-second WAV in memory to return from mock synthesize
        import io
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\x00\x00" * 24000)
        fake_wav_bytes = buf.getvalue()

        async def fake_audio_query(text, speaker, **kwargs):
            return {"speedScale": 1.1, "volumeScale": 1.0}

        async def fake_synthesize(query, speaker):
            return fake_wav_bytes

        with patch("pipeline.tts.synthesize.VoicevoxClient") as MockClient:
            instance = AsyncMock()
            instance.audio_query = AsyncMock(side_effect=fake_audio_query)
            instance.synthesize = AsyncMock(side_effect=fake_synthesize)
            MockClient.return_value = instance

            from pipeline.tts.synthesize import synthesize_all
            segments = synthesize_all(video_id=video_id, speaker=3, speed_scale=1.1, force=True)

        # Only chunks with narration_ja should be processed (chunk_id 1 and 2)
        assert len(segments) == 2
        assert segments[0].chunk_id == 1
        assert segments[1].chunk_id == 2

        # WAV files should exist
        assert (tmp_path / "output" / video_id / "audio" / "0001.wav").exists()
        assert (tmp_path / "output" / video_id / "audio" / "0002.wav").exists()

        # narration_segments.json should exist and be valid
        seg_path = tmp_path / "output" / video_id / "narration_segments.json"
        assert seg_path.exists()
        raw = json.loads(seg_path.read_text(encoding="utf-8"))
        assert len(raw) == 2
        loaded = [NarrationSegment.model_validate(s) for s in raw]
        assert loaded[0].audio_file == "audio/0001.wav"
        assert loaded[1].audio_file == "audio/0002.wav"

        # durations should match the 1-second WAV we wrote
        for seg in loaded:
            assert abs(seg.audio_duration - 1.0) < 0.05

    def test_synthesize_all_idempotent(self, tmp_path, monkeypatch):
        video_id = "DEMO0000002"
        self._make_chunks_json(tmp_path, video_id)
        monkeypatch.chdir(tmp_path)

        import io
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\x00\x00" * 24000)
        fake_wav_bytes = buf.getvalue()

        call_count = {"n": 0}

        async def fake_audio_query(text, speaker, **kwargs):
            call_count["n"] += 1
            return {"speedScale": 1.1}

        async def fake_synthesize(query, speaker):
            return fake_wav_bytes

        with patch("pipeline.tts.synthesize.VoicevoxClient") as MockClient:
            instance = AsyncMock()
            instance.audio_query = AsyncMock(side_effect=fake_audio_query)
            instance.synthesize = AsyncMock(side_effect=fake_synthesize)
            MockClient.return_value = instance

            from pipeline.tts.synthesize import synthesize_all
            # First run
            synthesize_all(video_id=video_id, speaker=3, speed_scale=1.1, force=False)
            first_count = call_count["n"]

            # Second run without force — should skip already-generated files
            synthesize_all(video_id=video_id, speaker=3, speed_scale=1.1, force=False)
            second_count = call_count["n"]

        assert first_count == 2  # two chunks with narration_ja
        assert second_count == first_count  # no new calls on second run

    def test_synthesize_all_missing_chunks_json(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "output" / "NODEMO00001").mkdir(parents=True)

        from pipeline.tts.synthesize import synthesize_all
        with pytest.raises(FileNotFoundError):
            synthesize_all(video_id="NODEMO00001", speaker=3)

    def test_overflow_triggers_resynth_at_higher_speed(self, tmp_path, monkeypatch):
        """Issue F: chunk whose audio overflows target by >10% is re-synthesized
        at a higher speed_scale. Mock makes audio_duration = base / speed_scale."""
        import io
        import wave

        video_id = "OVRFLW00001"
        video_dir = tmp_path / "output" / video_id
        video_dir.mkdir(parents=True)
        # 10s target, but at speed=1.1 the mock returns 13s audio (overflow).
        chunks = [
            {
                "chunk_id": 1,
                "start": 0.0,
                "end": 10.0,
                "items": [1],
                "text_en": "Long narration.",
                "subtitle_ja": "長いナレーション。",
                "narration_ja": "とても長いナレーションです。",
            }
        ]
        (video_dir / "chunks.json").write_text(
            json.dumps(chunks, ensure_ascii=False), encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)

        # base_duration at speed_scale=1.0 -> 14.3s
        # audio_duration(speed) = base / speed
        BASE = 14.3
        speed_history: list[float] = []

        def _wav_bytes(duration_s: float) -> bytes:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(b"\x00\x00" * int(24000 * duration_s))
            return buf.getvalue()

        async def fake_audio_query(text, speaker, speed_scale=1.1, **kwargs):
            speed_history.append(speed_scale)
            return {"speedScale": speed_scale, "_speed": speed_scale}

        async def fake_synthesize(query, speaker):
            speed = query.get("_speed", query.get("speedScale", 1.1))
            return _wav_bytes(BASE / speed)

        with patch("pipeline.tts.synthesize.VoicevoxClient") as MockClient:
            instance = AsyncMock()
            instance.audio_query = AsyncMock(side_effect=fake_audio_query)
            instance.synthesize = AsyncMock(side_effect=fake_synthesize)
            MockClient.return_value = instance

            from pipeline.tts.synthesize import synthesize_all
            segments = synthesize_all(
                video_id=video_id, speaker=3, speed_scale=1.1, force=True
            )

        # First attempt at 1.1 -> 14.3/1.1 = 13.0s (overflow vs 10s * 1.1 = 11s slack).
        # Re-synth at a higher speed should have been requested.
        assert len(speed_history) >= 2, f"expected re-synth, got speeds={speed_history}"
        assert speed_history[-1] > speed_history[0]
        # Final audio should be at-or-near target (under target * 1.10).
        assert segments[0].audio_duration <= 10.0 * 1.10 + 0.5

    def test_overflow_resynth_caps_at_max_speed(self, tmp_path, monkeypatch):
        """Computed new_speed must never exceed 1.5."""
        import io
        import wave

        video_id = "OVRFLW00002"
        video_dir = tmp_path / "output" / video_id
        video_dir.mkdir(parents=True)
        chunks = [
            {
                "chunk_id": 1,
                "start": 0.0,
                "end": 5.0,
                "items": [1],
                "text_en": "Way too much.",
                "subtitle_ja": "長すぎる。",
                "narration_ja": "極端に長いナレーション。",
            }
        ]
        (video_dir / "chunks.json").write_text(
            json.dumps(chunks, ensure_ascii=False), encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)

        BASE = 50.0  # huge overflow at any reasonable speed
        speed_history: list[float] = []

        def _wav_bytes(duration_s: float) -> bytes:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(b"\x00\x00" * int(24000 * duration_s))
            return buf.getvalue()

        async def fake_audio_query(text, speaker, speed_scale=1.1, **kwargs):
            speed_history.append(speed_scale)
            return {"speedScale": speed_scale, "_speed": speed_scale}

        async def fake_synthesize(query, speaker):
            speed = query.get("_speed", query.get("speedScale", 1.1))
            return _wav_bytes(BASE / speed)

        with patch("pipeline.tts.synthesize.VoicevoxClient") as MockClient:
            instance = AsyncMock()
            instance.audio_query = AsyncMock(side_effect=fake_audio_query)
            instance.synthesize = AsyncMock(side_effect=fake_synthesize)
            MockClient.return_value = instance

            from pipeline.tts.synthesize import synthesize_all
            synthesize_all(video_id=video_id, speaker=3, speed_scale=1.1, force=True)

        assert max(speed_history) <= 1.5 + 1e-6

    def test_no_overflow_no_resynth(self, tmp_path, monkeypatch):
        """Audio within target * 1.10 must not trigger re-synth."""
        import io
        import wave

        video_id = "OKDUR000001"
        video_dir = tmp_path / "output" / video_id
        video_dir.mkdir(parents=True)
        chunks = [
            {
                "chunk_id": 1,
                "start": 0.0,
                "end": 10.0,
                "items": [1],
                "text_en": "Short.",
                "subtitle_ja": "短い。",
                "narration_ja": "短いです。",
            }
        ]
        (video_dir / "chunks.json").write_text(
            json.dumps(chunks, ensure_ascii=False), encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)

        speed_history: list[float] = []
        # Produce 9s audio (under 10s target -> no overflow).
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\x00\x00" * int(24000 * 9.0))
        wav_bytes = buf.getvalue()

        async def fake_audio_query(text, speaker, speed_scale=1.1, **kwargs):
            speed_history.append(speed_scale)
            return {"speedScale": speed_scale}

        async def fake_synthesize(query, speaker):
            return wav_bytes

        with patch("pipeline.tts.synthesize.VoicevoxClient") as MockClient:
            instance = AsyncMock()
            instance.audio_query = AsyncMock(side_effect=fake_audio_query)
            instance.synthesize = AsyncMock(side_effect=fake_synthesize)
            MockClient.return_value = instance

            from pipeline.tts.synthesize import synthesize_all
            synthesize_all(video_id=video_id, speaker=3, speed_scale=1.1, force=True)

        assert speed_history == [1.1]


# ---------------------------------------------------------------------------
# Integration test — real VOICEVOX (skipped if not running)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestVoicevoxIntegration:
    @pytest.mark.asyncio
    async def test_health_check_live(self):
        client = VoicevoxClient()
        available = await client.health_check()
        if not available:
            pytest.skip("VOICEVOX Engine not running on localhost:50021")
        assert available is True

    @pytest.mark.asyncio
    async def test_audio_query_and_synth_live(self):
        client = VoicevoxClient()
        available = await client.health_check()
        if not available:
            pytest.skip("VOICEVOX Engine not running on localhost:50021")

        query = await client.audio_query(text="テスト", speaker=3, speed_scale=1.1)
        assert "speedScale" in query

        wav_bytes = await client.synthesize(query=query, speaker=3)
        assert wav_bytes[:4] == b"RIFF"
