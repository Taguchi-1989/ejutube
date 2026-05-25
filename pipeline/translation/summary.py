"""Per-video summary + auto-extracted glossary (section 8.14)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .backends import get_backend
from .glossary import load_video_glossary
from ._io import load_chunks, output_dir


_MAX_TOKENS = 2500


_SYSTEM_TEXT = (
    "あなたは英語チュートリアル動画の日本語学習用サマリー作成者です。\n"
    "出力は厳密に次の Markdown フォーマットのみ:\n"
    "\n"
    "# 要約 — {タイトル}\n"
    "\n"
    "## 概要 (200字)\n"
    "<200字以内の日本語要約>\n"
    "\n"
    "## チャンク別要点\n"
    "- Chunk 1 (mm:ss–mm:ss): <一文要点>\n"
    "- Chunk 2 (...): ...\n"
    "\n"
    "## 実装で試すべきポイント\n"
    "- ...\n"
    "\n"
    "## 注意点\n"
    "- ...\n"
    "\n"
    "## 自動抽出用語\n"
    "```json\n"
    "{ \"<英語>\": \"<日本語訳>\", ... }\n"
    "```\n"
    "\n"
    "ルール:\n"
    "- 動画内に存在しない情報を補わない。\n"
    "- 技術用語・プロダクト名・コマンドは原文表記を残す。\n"
    "- 自動抽出用語には既存辞書に無い専門用語のみ。なければ {} を出力。\n"
    "\n"
    "OUTPUT ONLY THE MARKDOWN — NO PREAMBLE, NO EXPLANATION."
)


def _fmt_ts(s: float) -> str:
    m = int(s // 60)
    sec = int(s % 60)
    return f"{m:02d}:{sec:02d}"


def _build_user(title: str, chunks, existing_glossary: dict[str, str]) -> str:
    parts = [f"動画タイトル: {title}", "", "既存の用語辞書（重複除外用）:", json.dumps(existing_glossary, ensure_ascii=False), ""]
    parts.append("以下が動画のチャンク別ナレーション（日本語）です。\n")
    for c in chunks:
        ts = f"{_fmt_ts(c.start)}–{_fmt_ts(c.end)}"
        parts.append(f"### Chunk {c.chunk_id} ({ts})")
        parts.append("EN:")
        parts.append(c.text_en)
        if c.narration_ja:
            parts.append("JA:")
            parts.append(c.narration_ja)
        parts.append("")
    parts.append("指定フォーマットに従い Markdown を出力してください。")
    return "\n".join(parts)


def _extract_glossary_block(md: str) -> dict[str, str]:
    marker = "## 自動抽出用語"
    if marker not in md:
        return {}
    tail = md.split(marker, 1)[1]
    if "```json" not in tail:
        return {}
    body = tail.split("```json", 1)[1].split("```", 1)[0].strip()
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def _load_title(video_id: str) -> str:
    meta = output_dir(video_id) / "metadata.json"
    if not meta.exists():
        return video_id
    try:
        return json.loads(meta.read_text(encoding="utf-8")).get("title", video_id)
    except json.JSONDecodeError:
        return video_id


def summarize(video_id: str) -> Path:
    chunks = load_chunks(video_id)
    existing = load_video_glossary(video_id)
    title = _load_title(video_id)
    backend = get_backend()
    user = _build_user(title, chunks, existing)

    md = asyncio.run(
        backend.chat(
            system=_SYSTEM_TEXT,
            user=user,
            max_tokens=_MAX_TOKENS,
            temperature=0.2,
        )
    )
    if not md.strip():
        raise RuntimeError("Empty summary response")

    summary_path = output_dir(video_id) / "summary.md"
    summary_path.write_text(md, encoding="utf-8")

    extracted = _extract_glossary_block(md)
    if extracted:
        new_entries = {k: v for k, v in extracted.items() if k not in existing}
        if new_entries:
            override_path = output_dir(video_id) / "glossary.json"
            existing_override: dict[str, str] = {}
            if override_path.exists():
                try:
                    existing_override = {
                        k: v
                        for k, v in json.loads(override_path.read_text(encoding="utf-8")).items()
                        if isinstance(k, str) and isinstance(v, str) and not k.startswith("_")
                    }
                except json.JSONDecodeError:
                    existing_override = {}
            existing_override.update(new_entries)
            override_path.write_text(
                json.dumps(existing_override, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    return summary_path
