"""Generate narration_ja per chunk (section 8.7)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from pipeline.models import Chunk

from .backends import get_backend
from .glossary import load_video_glossary
from ._io import load_chunks, output_dir, save_chunks


_MAX_TOKENS = 500
_TEMPERATURE = 0.2


def _concurrency() -> int:
    backend = get_backend()
    return 2 if backend.name == "ollama" else 5


def _system_prompt(glossary: dict[str, str]) -> str:
    glossary_json = json.dumps(glossary, ensure_ascii=False)
    return (
        "あなたは英語チュートリアル動画の日本語ナレーション台本作成者です。\n"
        "成果物は TTS で読み上げられます。\n"
        "重要: 字幕とは異なる文章にすること。同一にしてはならない。\n"
        "字幕は読む文、ナレーションは耳で聞く文。語順・接続・分割を変える。\n"
        "ルール:\n"
        "- 1文を短く切る。各「。」までは目安 25 文字以下。\n"
        "- 文頭に「では、」「次に、」「ここで、」「まず、」「さて、」を積極的に使う。\n"
        "- 字幕で1文だった内容は、ナレーションでは2文以上に分割する。\n"
        "- 不自然な直訳を避ける。ただし、原文にない情報の追加・手順の入れ替えは禁止。\n"
        "- 技術用語・プロダクト名・コマンド・ファイル名・パスは原文のまま読む形で残す。\n"
        "- 敬体（です・ます調）。\n"
        f"用語辞書: {glossary_json}\n"
        "\n"
        "例1（字幕とナレーションを必ず変える）:\n"
        "EN: Now let's open Cursor and connect it with Claude Code.\n"
        "字幕: Cursor を開き、Claude Code と接続します。\n"
        "ナレーション: では、ここで Cursor を開きます。次に、Claude Code に接続しましょう。\n"
        "\n"
        "例2:\n"
        "EN: Open your terminal and run npm install.\n"
        "字幕: ターミナルを開いて npm install を実行します。\n"
        "ナレーション: まず、ターミナルを開きます。そして、npm install を実行します。\n"
        "\n"
        "OUTPUT ONLY THE JAPANESE NARRATION TEXT — NO PREAMBLE, NO QUOTES, NO BULLETS, NO EXPLANATION."
    )


def _user_prompt(prev: Chunk | None, current: Chunk, nxt: Chunk | None) -> str:
    parts = ["CURRENT を TTS 読み上げ用の日本語ナレーションに書き起こしてください。PREV/NEXT は文脈用。\n"]
    if prev is not None:
        parts.append(f"[PREV]\n{prev.text_en}\n")
    parts.append(f"[CURRENT]\n{current.text_en}\n")
    if nxt is not None:
        parts.append(f"[NEXT]\n{nxt.text_en}\n")
    if current.subtitle_ja:
        parts.append(
            "[DO NOT MATCH THIS — 字幕（同じ文章にしてはならない）]\n"
            f"{current.subtitle_ja}\n"
            "上の字幕とは語順・接続・分割を変え、必ず異なる文章にすること。\n"
        )
    parts.append("CURRENT の読み上げ用日本語ナレーションのみを出力。")
    return "\n".join(parts)


async def _narrate_one(
    sem: asyncio.Semaphore,
    backend,
    system: str,
    prev: Chunk | None,
    current: Chunk,
    nxt: Chunk | None,
) -> str:
    async with sem:
        user = _user_prompt(prev, current, nxt)
        text = await backend.chat(
            system=system, user=user, max_tokens=_MAX_TOKENS, temperature=_TEMPERATURE
        )
        out = text.strip()
        if not out:
            stricter = user + "\n\n注意: 日本語ナレーション本文のみを出力。空応答や前置きは禁止。"
            text = await backend.chat(
                system=system, user=stricter, max_tokens=_MAX_TOKENS, temperature=_TEMPERATURE
            )
            out = text.strip()
            if not out:
                raise RuntimeError(f"Empty narration for chunk_id={current.chunk_id}")
        return out


async def _narrate_all(chunks: list[Chunk], glossary: dict[str, str]) -> list[Chunk]:
    backend = get_backend()
    system = _system_prompt(glossary)
    sem = asyncio.Semaphore(_concurrency())
    tasks = []
    for i, c in enumerate(chunks):
        prev = chunks[i - 1] if i > 0 else None
        nxt = chunks[i + 1] if i + 1 < len(chunks) else None
        tasks.append(_narrate_one(sem, backend, system, prev, c, nxt))
    results = await asyncio.gather(*tasks)
    for c, na in zip(chunks, results):
        c.narration_ja = na
    return chunks


def _write_script_md(video_id: str, chunks: list[Chunk]) -> Path:
    path = output_dir(video_id) / "narration.script.md"
    lines = [f"# Narration script — {video_id}", ""]
    for c in chunks:
        lines.append(f"## Chunk {c.chunk_id}  ({c.start:.1f}s – {c.end:.1f}s)")
        lines.append("")
        lines.append("**EN:**")
        lines.append("")
        lines.append(c.text_en)
        lines.append("")
        if c.subtitle_ja:
            lines.append("**字幕 (JA):**")
            lines.append("")
            lines.append(c.subtitle_ja)
            lines.append("")
        lines.append("**ナレーション (JA):**")
        lines.append("")
        lines.append(c.narration_ja or "")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def narrate_chunks(video_id: str) -> list[Chunk]:
    chunks = load_chunks(video_id)
    glossary = load_video_glossary(video_id)
    chunks = asyncio.run(_narrate_all(chunks, glossary))
    save_chunks(video_id, chunks)
    _write_script_md(video_id, chunks)
    return chunks
