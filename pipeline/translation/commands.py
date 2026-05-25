"""Extract verbatim shell commands / paths / config keys (section 8.15)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .backends import get_backend
from ._io import output_dir


_MAX_TOKENS = 1500


_SYSTEM_TEXT = (
    "あなたは英語チュートリアル動画からコマンド・ファイルパス・設定値を抽出する作業者です。\n"
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
    "- <verbatim config key, env var, hotkey, URL, port>\n"
    "\n"
    "厳格ルール (verbatim extraction, no invention):\n"
    "- 動画の英語字幕に明示的に出てきたもののみを抽出する。\n"
    "- 推測でコマンドや引数を絶対に補わない。\n"
    "- 推測したくなったら、その項目は省略する。\n"
    "- コマンドは英語原文のままコピー。日本語化しない。\n"
    "- 該当項目が無いセクションは「- (なし)」と書く。\n"
    "\n"
    "OUTPUT ONLY THE MARKDOWN — NO PREAMBLE, NO EXPLANATION."
)


def _build_user(items: list[dict]) -> str:
    lines = ["以下が動画の英語字幕（時刻付き）です。\n"]
    for it in items:
        lines.append(f"[{it['start']:.1f}s] {it['text_en']}")
    lines.append("\n指定フォーマットの Markdown を出力してください。verbatim のみ。")
    return "\n".join(lines)


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

    out = output_dir(video_id) / "commands.md"
    out.write_text(md, encoding="utf-8")
    return out
