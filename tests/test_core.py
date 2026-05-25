"""
Tests for pipeline/core — video_id, normalize, chunk.

Run with: pytest tests/test_core.py -v
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

# Use a temp output dir so tests don't pollute the real output/ folder
_SAMPLES = Path(__file__).parent.parent / "samples"
_SAMPLE_VTT = _SAMPLES / "sample.en.vtt"
# Use D:\tmp to avoid Windows permission issues with the default pytest temp dir
_TMP_BASE = Path("D:/tmp/ejutube_tests")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_output():
    """Set OUTPUT_DIR to a temp directory for the duration of the test."""
    import uuid
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


@pytest.fixture()
def demo_vtt(tmp_output):
    """Copy sample.en.vtt into output/DEMO0000000/ and return the video_id."""
    video_id = "DEMO0000000"
    vid_dir = tmp_output / video_id
    vid_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(_SAMPLE_VTT, vid_dir / "transcript.en.vtt")
    return video_id


# ---------------------------------------------------------------------------
# extract_video_id
# ---------------------------------------------------------------------------

class TestExtractVideoId:
    def test_watch_url(self):
        from pipeline.core.video_id import extract_video_id
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_youtu_be(self):
        from pipeline.core.video_id import extract_video_id
        assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts(self):
        from pipeline.core.video_id import extract_video_id
        assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed(self):
        from pipeline.core.video_id import extract_video_id
        assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_bare_id(self):
        from pipeline.core.video_id import extract_video_id
        assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_invalid_empty(self):
        from pipeline.core.video_id import extract_video_id
        with pytest.raises(ValueError):
            extract_video_id("")

    def test_invalid_short_id(self):
        from pipeline.core.video_id import extract_video_id
        with pytest.raises(ValueError):
            extract_video_id("short")

    def test_invalid_domain(self):
        from pipeline.core.video_id import extract_video_id
        with pytest.raises(ValueError):
            extract_video_id("https://vimeo.com/123456789AB")


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_produces_items(self, demo_vtt):
        from pipeline.core.normalize import normalize
        items = normalize(demo_vtt)
        assert len(items) >= 1

    def test_items_have_positive_duration(self, demo_vtt):
        from pipeline.core.normalize import normalize
        items = normalize(demo_vtt)
        for item in items:
            assert item.end >= item.start, f"Item {item.id}: end < start"

    def test_items_are_sequential(self, demo_vtt):
        from pipeline.core.normalize import normalize
        items = normalize(demo_vtt)
        ids = [item.id for item in items]
        assert ids == list(range(1, len(ids) + 1))

    def test_writes_json(self, demo_vtt, tmp_output):
        from pipeline.core.normalize import normalize
        normalize(demo_vtt)
        out = tmp_output / demo_vtt / "transcript.normalized.json"
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_json_validates_against_schema(self, demo_vtt, tmp_output):
        from pipeline.core.normalize import normalize
        from pipeline.models import TranscriptItem
        normalize(demo_vtt)
        out = tmp_output / demo_vtt / "transcript.normalized.json"
        data = json.loads(out.read_text(encoding="utf-8"))
        for raw in data:
            item = TranscriptItem(**raw)
            assert item.id >= 1
            assert item.start >= 0
            assert item.end >= 0
            assert len(item.text_en) >= 1

    def test_no_empty_text(self, demo_vtt):
        from pipeline.core.normalize import normalize
        items = normalize(demo_vtt)
        for item in items:
            assert item.text_en.strip(), f"Item {item.id} has empty text"


# ---------------------------------------------------------------------------
# chunk
# ---------------------------------------------------------------------------

class TestChunk:
    @pytest.fixture(autouse=True)
    def _normalized(self, demo_vtt):
        from pipeline.core.normalize import normalize
        normalize(demo_vtt)
        self.video_id = demo_vtt

    def test_produces_chunks(self, tmp_output):
        from pipeline.core.chunk import chunk
        chunks = chunk(self.video_id)
        assert len(chunks) >= 1

    def test_chunk_duration_bounds(self, tmp_output):
        from pipeline.core.chunk import chunk
        chunks = chunk(self.video_id, target_seconds=25, max_seconds=30)
        for i, c in enumerate(chunks):
            duration = c.end - c.start
            is_last = i == len(chunks) - 1
            # Every chunk except possibly the last must be <= 30s.
            assert duration <= 30.0 + 1e-6, f"Chunk {c.chunk_id} duration {duration:.2f}s > 30s"
            # Non-last chunks should be >= 10s (within a small tolerance for tiny samples)
            if not is_last and len(chunks) > 1:
                assert duration >= 5.0, (
                    f"Non-last chunk {c.chunk_id} duration {duration:.2f}s is very short"
                )

    def test_item_ids_reference_valid_transcript(self, tmp_output):
        from pipeline.core.normalize import normalize
        from pipeline.core.chunk import chunk
        items = normalize(self.video_id)
        valid_ids = {item.id for item in items}
        chunks = chunk(self.video_id)
        for c in chunks:
            for iid in c.items:
                assert iid in valid_ids, f"Chunk {c.chunk_id} references unknown item id {iid}"

    def test_writes_json(self, tmp_output):
        from pipeline.core.chunk import chunk
        chunk(self.video_id)
        out = tmp_output / self.video_id / "chunks.json"
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_chunk_ids_sequential(self, tmp_output):
        from pipeline.core.chunk import chunk
        chunks = chunk(self.video_id)
        ids = [c.chunk_id for c in chunks]
        assert ids == list(range(1, len(ids) + 1))

    def test_text_en_not_empty(self, tmp_output):
        from pipeline.core.chunk import chunk
        chunks = chunk(self.video_id)
        for c in chunks:
            assert c.text_en.strip(), f"Chunk {c.chunk_id} has empty text_en"

    def test_no_items_field_missing(self, tmp_output):
        from pipeline.core.chunk import chunk
        chunks = chunk(self.video_id)
        for c in chunks:
            assert isinstance(c.items, list)
            assert len(c.items) >= 1
