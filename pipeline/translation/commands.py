"""Extract verbatim shell commands / paths / config keys (section 8.15)."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from .backends import get_backend
from ._io import output_dir


_MAX_TOKENS = 1500


_SYSTEM_TEXT = (
    "あなたは英語チュートリアル動画からコマンド・ファイル名・設定値を抽出する作業者です。\n"
    "出力は Markdown のみ。次の固定セクションを順に出力:\n"
    "\n"
    "# Commands\n"
    "```bash\n"
    "<verbatim shell commands, 1行ずつ。なければ # (なし)>\n"
    "```\n"
    "\n"
    "# Files\n"
    "- <verbatim file path or filename>\n"
    "\n"
    "# Config / Keys\n"
    "- <verbatim config key, env var, hotkey, slash command, URL>\n"
    "\n"
    "原文から以下のカテゴリに該当する文字列を1回でも出現していれば必ず抽出せよ:\n"
    "1. シェルコマンド: npm/yarn/pnpm/git/yt-ja/python/pip/curl/docker/node などで始まる行。\n"
    "2. ファイル/パス名: 拡張子付き (例: package.json, README.md, app.tsx, main.py) または / を含むパス。\n"
    "3. ホットキー/ショートカット: Command/Ctrl/Shift/Alt + 文字 (例: Command Shift P, Ctrl+C)。\n"
    "4. スラッシュコマンド: / で始まる短い識別子 (例: /init, /clear, /help)。\n"
    "5. URL/エンドポイント: http:// または /api/ で始まる文字列。\n"
    "6. 環境変数: 全大文字 + アンダースコア (例: ANTHROPIC_API_KEY, NODE_ENV)。\n"
    "7. CLI フラグ: -- で始まる単語 (例: --force, --help)。\n"
    "\n"
    "「動画内に明示的に出現した」ものだけ。出現していないものを推測で追加するな。\n"
    "コマンドは英語原文のままコピー。日本語化しない。\n"
    "該当項目が無いセクションは「- (なし)」と書く（Commands は # (なし)）。\n"
    "\n"
    "例:\n"
    "原文: \"Press Command Shift P to open the palette, then type /init and run npm install. "
    "Check package.json and /api/status.\"\n"
    "抽出:\n"
    "# Commands\n"
    "```bash\n"
    "npm install\n"
    "```\n"
    "# Files\n"
    "- package.json\n"
    "# Config / Keys\n"
    "- Command Shift P\n"
    "- /init\n"
    "- /api/status\n"
    "\n"
    "OUTPUT ONLY THE MARKDOWN — NO PREAMBLE, NO EXPLANATION."
)


def _build_user(items: list[dict]) -> str:
    lines = ["以下が動画の英語字幕（時刻付き）です。\n"]
    for it in items:
        lines.append(f"[{it['start']:.1f}s] {it['text_en']}")
    lines.append("\n指定フォーマットの Markdown を出力してください。verbatim のみ。")
    return "\n".join(lines)


# Lines that are structural / non-content and should never be dropped by the filter.
_STRUCTURAL_RE = re.compile(
    r"^\s*(#|```|-\s*\(なし\)\s*$|#\s*\(なし\)\s*$|$)"
)


def _normalize(s: str) -> str:
    """Lowercase + collapse whitespace + strip surrounding punctuation."""
    return re.sub(r"\s+", " ", s.lower()).strip().strip("`'\"() ")


def _filter_hallucinations(md: str, transcript_text: str) -> str:
    """Drop bullet/code lines whose payload doesn't appear in the transcript.

    This prevents the model from inventing commands/paths/keys. Structural
    markdown (headings, fences, "(なし)") is preserved untouched.

    Uses word-boundary lookarounds (not \\b) so that tokens with non-word
    prefix characters (e.g. /init, --force) are matched correctly without
    also matching substrings inside longer words (e.g. /init inside
    'initialize').
    """
    haystack = _normalize(transcript_text)
    kept: list[str] = []
    in_code = False
    for line in md.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            kept.append(line)
            continue
        if _STRUCTURAL_RE.match(line):
            kept.append(line)
            continue

        # Extract the payload to check: bullets strip leading "- ".
        if stripped.startswith("- "):
            payload = stripped[2:].strip()
        else:
            payload = stripped

        if not payload:
            kept.append(line)
            continue

        needle = _normalize(payload)
        # Skip filtering for very short payloads (too noisy to gate reliably).
        if len(needle) < 4:
            kept.append(line)
            continue

        # Use word-boundary lookarounds so that e.g. "/init" does not match
        # inside "initialize", and "npm" does not match inside "Olympic npm".
        pattern = rf"(?<!\w){re.escape(needle)}(?!\w)"
        if needle and re.search(pattern, haystack):
            kept.append(line)
        # else: drop the line (hallucination)
    return "\n".join(kept)


def extract_commands(video_id: str) -> Path:
    normalized_path = output_dir(video_id) / "transcript.normalized.json"
    if not normalized_path.exists():
        raise FileNotFoundError(
            f"{normalized_path} not found. Run `yt-ja normalize` first."
        )
    items = json.loads(normalized_path.read_text(encoding="utf-8"))

    backend = get_backend()
    user = _build_user(items)

    md = asyncio.run(
        backend.chat(
            system=_SYSTEM_TEXT,
            user=user,
            max_tokens=_MAX_TOKENS,
            temperature=0.0,
        )
    )
    if not md.strip():
        raise RuntimeError("Empty commands response")

    # Post-filter: drop any extracted entry not present in the transcript.
    transcript_text = " ".join(it.get("text_en", "") for it in items)
    md = _filter_hallucinations(md, transcript_text)

    out = output_dir(video_id) / "commands.md"
    out.write_text(md, encoding="utf-8")
    return out
