"""Generate subtitle_ja for each chunk (section 8.6)."""

from __future__ import annotations

import asyncio
import json

from pipeline.models import Chunk

from .backends import get_backend
from .glossary import load_video_glossary
from ._io import load_chunks, save_chunks


_MAX_TOKENS = 400
_TEMPERATURE = 0.2


def _concurrency() -> int:
    backend = get_backend()
    return 2 if backend.name == "ollama" else 5


def _system_prompt(glossary: dict[str, str]) -> str:
    glossary_json = json.dumps(glossary, ensure_ascii=False)
    return (
        "あなたは英語チュートリアル動画の日本語字幕翻訳者です。\n"
        "ルール:\n"
        "- 原文の意味を忠実に保つ。補足・要約・解釈をしない。\n"
        "- 技術用語・プロダクト名・コマンド・ファイル名・パス・URL・キー操作は原文のまま残す。\n"
        "- 用語辞書に従い訳語を統一する。\n"
        "- CURRENT に含まれる全ての文を翻訳する（省略禁止）。\n"
        "- 各文を1行に収め、文の区切りで改行する。\n"
        "- 敬体（です・ます調）。\n"
        f"用語辞書: {glossary_json}\n"
        "\n"
        "例:\n"
        "EN: Welcome to this tutorial on Claude Code and Cursor.\n"
        "JA: Claude Code と Cursor のチュートリアルへようこそ。\n"
        "EN: Open your terminal and navigate to your project repository.\n"
        "JA: ターミナルを開き、プロジェクトのリポジトリに移動します。\n"
        "\n"
        "OUTPUT ONLY THE JAPANESE TRANSLATION — NO PREAMBLE, NO QUOTES, NO EXPLANATION."
    )


def _user_prompt(prev: Chunk | None, current: Chunk, nxt: Chunk | None) -> str:
    parts = ["CURRENT を日本語に翻訳してください。PREV/NEXT は文脈用、翻訳しない。\n"]
    if prev is not None:
        parts.append(f"[PREV]\n{prev.text_en}\n")
    parts.append(f"[CURRENT]\n{current.text_en}\n")
    if nxt is not None:
        parts.append(f"[NEXT]\n{nxt.text_en}\n")
    parts.append("CURRENT の日本語訳のみを1行で出力。")
    return "\n".join(parts)


def _strip(text: str) -> str:
    text = text.strip()
    for q in ('"', "'", "「", "『"):
        if text.startswith(q):
            text = text[len(q):]
            break
    for q in ('"', "'", "」", "』"):
        if text.endswith(q):
            text = text[: -len(q)]
            break
    return text.strip()


async def _translate_one(
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
        out = _strip(text)
        if not out:
            stricter = user + "\n\n注意: 日本語訳1文のみ。空応答や前置きは禁止。"
            text = await backend.chat(
                system=system, user=stricter, max_tokens=_MAX_TOKENS, temperature=_TEMPERATURE
            )
            out = _strip(text)
            if not out:
                raise RuntimeError(f"Empty translation for chunk_id={current.chunk_id}")
        return out


async def _translate_all(chunks: list[Chunk], glossary: dict[str, str]) -> list[Chunk]:
    backend = get_backend()
    system = _system_prompt(glossary)
    sem = asyncio.Semaphore(_concurrency())
    tasks = []
    for i, c in enumerate(chunks):
        prev = chunks[i - 1] if i > 0 else None
        nxt = chunks[i + 1] if i + 1 < len(chunks) else None
        tasks.append(_translate_one(sem, backend, system, prev, c, nxt))
    results = await asyncio.gather(*tasks)
    for c, ja in zip(chunks, results):
        c.subtitle_ja = ja
    return chunks


def translate_chunks(video_id: str) -> list[Chunk]:
    chunks = load_chunks(video_id)
    glossary = load_video_glossary(video_id)
    chunks = asyncio.run(_translate_all(chunks, glossary))
    save_chunks(video_id, chunks)
    return chunks
