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
# Issue H: narrate prompt must reference the subtitle as anti-example
# ---------------------------------------------------------------------------


def test_narrate_user_prompt_includes_subtitle_anti_example():
    """The user prompt must contain the subtitle marked as DO NOT MATCH."""
    chunk = Chunk(
        chunk_id=1,
        start=0.0,
        end=10.0,
        items=[1],
        text_en="Open Cursor and connect Claude Code.",
        subtitle_ja="Cursor を開き、Claude Code と接続します。",
    )
    prompt = nmod._user_prompt(prev=None, current=chunk, nxt=None)
    assert "DO NOT MATCH" in prompt
    assert "Cursor を開き、Claude Code と接続します。" in prompt


def test_narrate_system_prompt_forbids_subtitle_identity():
    """The system prompt must explicitly forbid matching the subtitle."""
    system = nmod._system_prompt({})
    assert "字幕とは異なる" in system or "同一にしてはならない" in system


# ---------------------------------------------------------------------------
# Issue I: commands extraction post-filter
# ---------------------------------------------------------------------------


def test_commands_filter_keeps_present_items_drops_hallucinations():
    from pipeline.translation.commands import _filter_hallucinations

    transcript = (
        "Press Command Shift P to open the palette, then run npm install. "
        "Open package.json to check the deps."
    )
    md = (
        "# Commands\n"
        "```bash\n"
        "npm install\n"
        "rm -rf /\n"
        "```\n"
        "# Files\n"
        "- package.json\n"
        "- nonexistent.yaml\n"
        "# Config / Keys\n"
        "- Command Shift P\n"
        "- /api/fake\n"
    )
    filtered = _filter_hallucinations(md, transcript)
    assert "npm install" in filtered
    assert "package.json" in filtered
    assert "Command Shift P" in filtered
    # Hallucinations dropped
    assert "rm -rf /" not in filtered
    assert "nonexistent.yaml" not in filtered
    assert "/api/fake" not in filtered
    # Headers preserved
    assert "# Commands" in filtered
    assert "# Files" in filtered


def test_commands_filter_preserves_structural_lines():
    from pipeline.translation.commands import _filter_hallucinations

    md = (
        "# Commands\n"
        "```bash\n"
        "# (なし)\n"
        "```\n"
        "# Files\n"
        "- (なし)\n"
    )
    filtered = _filter_hallucinations(md, "irrelevant transcript text")
    assert "# Commands" in filtered
    assert "```" in filtered
    assert "(なし)" in filtered


def test_commands_filter_word_boundary_slash_command():
    """M3: /init extracted from transcript with 'initialize' should be DROPPED.

    Without word-boundary matching, '/init' would substring-match inside
    'initialize', causing a false negative (hallucination kept).
    With (?<!\\w)/init(?!\\w) the match fails and the line is correctly dropped.
    """
    from pipeline.translation.commands import _filter_hallucinations

    # Transcript says "initialize" — does NOT contain "/init" as a token.
    transcript = "Use the initialize command to set up your project."
    md = (
        "# Config / Keys\n"
        "- /init\n"
    )
    filtered = _filter_hallucinations(md, transcript)
    # /init must be dropped — it was not present as a standalone token.
    assert "/init" not in filtered


def test_commands_filter_word_boundary_keeps_real_slash_command():
    """M3: /init extracted from transcript that literally contains '/init' should be KEPT.

    'Command Shift P' extracted with actual 'Command Shift P' in transcript
    must also be kept.
    """
    from pipeline.translation.commands import _filter_hallucinations

    transcript = "Type /init and press Command Shift P to run the command."
    md = (
        "# Config / Keys\n"
        "- /init\n"
        "- Command Shift P\n"
        "- /phantom\n"
    )
    filtered = _filter_hallucinations(md, transcript)
    assert "/init" in filtered
    assert "Command Shift P" in filtered
    # /phantom is not in transcript — must be dropped.
    assert "/phantom" not in filtered


def test_commands_filter_cjk_adjacency():
    """Low 1: 'npm' adjacent to a CJK char must still be KEPT.

    Python re Unicode mode treats CJK chars as \\w, so the old
    (?<!\\w)npm(?!\\w) pattern would fail to match 'npm' in 'npmコマンドを実行'
    because 'コ' is a Unicode word char. The fix uses ASCII-only boundaries.
    """
    from pipeline.translation.commands import _filter_hallucinations

    transcript = "npmコマンドを実行してください。"
    md = (
        "# Commands\n"
        "```bash\n"
        "npm\n"
        "```\n"
    )
    filtered = _filter_hallucinations(md, transcript)
    assert "npm" in filtered, "npm adjacent to CJK should be KEPT"


def test_extract_commands_post_filters_hallucinations(tmp_path, monkeypatch):
    """End-to-end: mock LLM returns hallucinated entries; post-filter removes them."""
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("EJUTUBE_LLM_BACKEND", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    ab_mod.reset_client()
    client_mod.reset_client()

    video_id = "CMDTEST0001"
    out = tmp_path / video_id
    out.mkdir()
    items = [
        {"id": 1, "start": 0.0, "end": 5.0, "text_en": "Press Command Shift P."},
        {"id": 2, "start": 5.0, "end": 10.0, "text_en": "Then run npm install in your terminal."},
        {"id": 3, "start": 10.0, "end": 15.0, "text_en": "Check package.json afterward."},
    ]
    (out / "transcript.normalized.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )

    fake_md = (
        "# Commands\n"
        "```bash\n"
        "npm install\n"
        "git push origin main\n"
        "```\n"
        "# Files\n"
        "- package.json\n"
        "- secrets.env\n"
        "# Config / Keys\n"
        "- Command Shift P\n"
        "- /api/foo\n"
    )

    async def fake_create(**kwargs):
        return _fake_response(fake_md)

    from pipeline.translation.commands import extract_commands

    with patch.object(ab_mod, "get_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=fake_create)
        mock_get.return_value = mock_client
        path = extract_commands(video_id)

    result = path.read_text(encoding="utf-8")
    # Real items present in transcript
    assert "npm install" in result
    assert "package.json" in result
    assert "Command Shift P" in result
    # Hallucinations dropped
    assert "git push origin main" not in result
    assert "secrets.env" not in result
    assert "/api/foo" not in result


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
