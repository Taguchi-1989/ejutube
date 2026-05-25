"""Tests for pipeline/translation — glossary, translate, narrate, retry."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from anthropic import RateLimitError

from pipeline.models import Chunk
from pipeline.translation import glossary as gmod
from pipeline.translation import _io as iomod
from pipeline.translation import client as client_mod
from pipeline.translation.backends import anthropic_backend as ab_mod
from pipeline.translation import translate as tmod
from pipeline.translation import narrate as nmod


VIDEO_ID = "TESTVIDEO01"


def _make_chunks() -> list[Chunk]:
    return [
        Chunk(
            chunk_id=1,
            start=0.0,
            end=10.0,
            items=[1],
            text_en="Open your terminal and run npm install.",
        ),
        Chunk(
            chunk_id=2,
            start=10.0,
            end=20.0,
            items=[2],
            text_en="Then open Cursor and connect Claude Code.",
        ),
    ]


@pytest.fixture
def video_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("EJUTUBE_LLM_BACKEND", "anthropic")
    ab_mod.reset_client()
    client_mod.reset_client()
    out = tmp_path / VIDEO_ID
    out.mkdir(parents=True)
    chunks = _make_chunks()
    iomod.save_chunks(VIDEO_ID, chunks)
    return out


# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------


def test_load_glossary_strips_comment_keys():
    g = gmod.load_glossary()
    assert "_comment" not in g
    assert g.get("Cursor") == "Cursor"
    assert g.get("agent") == "エージェント"


def test_apply_glossary_is_identity():
    g = {"foo": "bar"}
    assert gmod.apply_glossary("hello foo", g) == "hello foo"


def test_video_glossary_override(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    (tmp_path / VIDEO_ID).mkdir()
    (tmp_path / VIDEO_ID / "glossary.json").write_text(
        json.dumps({"Foo": "フー"}), encoding="utf-8"
    )
    merged = gmod.load_video_glossary(VIDEO_ID)
    assert merged["Foo"] == "フー"
    assert merged["Cursor"] == "Cursor"


# ---------------------------------------------------------------------------
# Translate — mocked
# ---------------------------------------------------------------------------


def _fake_response(text: str):
    class _Block:
        type = "text"

        def __init__(self, t):
            self.text = t

    class _Resp:
        def __init__(self, t):
            self.content = [_Block(t)]

    return _Resp(text)


def test_translate_sets_subtitle_ja(video_dir):
    captured: dict = {}

    async def fake_create(**kwargs):
        captured["kwargs"] = kwargs
        captured.setdefault("calls", 0)
        captured["calls"] += 1
        return _fake_response("これはテスト訳です。")

    with patch.object(
        ab_mod, "get_client"
    ) as mock_get:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=fake_create)
        mock_get.return_value = mock_client

        chunks = tmod.translate_chunks(VIDEO_ID)

    assert captured["calls"] == 2
    for c in chunks:
        assert c.subtitle_ja == "これはテスト訳です。"

    # System prompt should contain glossary terms
    system = captured["kwargs"]["system"]
    assert any("Cursor" in b["text"] for b in system)
    assert any("cache_control" in b for b in system)

    # Round-trip: chunks.json must validate against the Pydantic model
    reloaded = iomod.load_chunks(VIDEO_ID)
    assert reloaded[0].subtitle_ja == "これはテスト訳です。"


def test_narrate_sets_narration_ja_and_writes_script(video_dir):
    async def fake_create(**kwargs):
        return _fake_response("では、ターミナルを開きます。次に、npm install を実行します。")

    with patch.object(ab_mod, "get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=fake_create)
        mock_get.return_value = mock_client

        chunks = nmod.narrate_chunks(VIDEO_ID)

    for c in chunks:
        assert c.narration_ja and "ターミナル" in c.narration_ja

    script = video_dir / "narration.script.md"
    assert script.exists()
    assert "Chunk 1" in script.read_text(encoding="utf-8")


def test_rate_limit_triggers_one_retry(video_dir):
    calls = {"n": 0}

    async def fake_create(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            # Construct a minimal RateLimitError
            raise RateLimitError(
                message="rate limited",
                response=_DummyResponse(),
                body=None,
            )
        return _fake_response("リトライ後の訳。")

    with patch.object(client_mod, "get_client") as mock_get, patch(
        "pipeline.translation.client.asyncio.sleep", new=AsyncMock()
    ):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=fake_create)
        mock_get.return_value = mock_client

        # Call directly to isolate retry behavior
        result = asyncio.run(
            client_mod.call_with_cache(
                system_blocks=[{"type": "text", "text": "sys"}],
                user="hi",
                model="claude-sonnet-4-6",
                max_tokens=100,
            )
        )

    assert result == "リトライ後の訳。"
    assert calls["n"] == 2


class _DummyResponse:
    status_code = 429
    headers: dict = {}

    def __init__(self):
        self.request = None


# ---------------------------------------------------------------------------
# Live integration test — hits real API on 2 chunks
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-"),
    reason="ANTHROPIC_API_KEY not set",
)
def test_translate_live(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    client_mod.reset_client()
    (tmp_path / VIDEO_ID).mkdir()
    iomod.save_chunks(VIDEO_ID, _make_chunks())

    chunks = tmod.translate_chunks(VIDEO_ID)
    for c in chunks:
        assert c.subtitle_ja and any(
            "぀" <= ch <= "ヿ" or "一" <= ch <= "鿿"
            for ch in c.subtitle_ja
        ), f"expected Japanese output, got: {c.subtitle_ja!r}"
