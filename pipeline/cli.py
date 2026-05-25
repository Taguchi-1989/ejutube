"""
yt-ja CLI — pipeline entry point.

Entry point: yt-ja = pipeline.cli:app  (see pyproject.toml)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

# Bug E fix: rich progress bar uses braille chars that crash on Windows cp932.
# Force UTF-8 on stdio so users don't need to set PYTHONIOENCODING manually.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

app = typer.Typer(
    name="yt-ja",
    help="YouTube英語チュートリアル日本語化パイプライン",
    no_args_is_help=True,
)

_VERSION = "0.1.0"

_STAGE_ORDER = [
    "metadata",
    "fetch-subtitle",
    "normalize",
    "chunk",
    "translate",
    "narrate",
    "tts",
    "sync",
    "completed",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _output_base() -> Path:
    return Path(os.environ.get("OUTPUT_DIR", "./output"))


def _output_exists(video_id: str, filename: str) -> bool:
    return (_output_base() / video_id / filename).exists()


def _stage_complete(video_id: str, field: str) -> bool:
    """True iff chunks.json exists AND every chunk has `field` set (non-None).

    M1 fix: use `is not None` (not truthiness) so that legitimately empty
    LLM output (e.g. music-only chunk) is treated as 'translated', not
    'pending'. Pydantic dumps the field as null until the stage runs.
    """
    import json
    path = _output_base() / video_id / "chunks.json"
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return bool(data) and all(c.get(field) is not None for c in data)
    except (json.JSONDecodeError, OSError):
        return False


def _translation_done(video_id: str) -> bool:
    return _stage_complete(video_id, "subtitle_ja")


def _narration_done(video_id: str) -> bool:
    return _stage_complete(video_id, "narration_ja")


def _chunks_newer_than_player(video_id: str) -> bool:
    """Bug A guard: chunks.json modified at-or-after player.json means re-sync.

    M2 fix: use >= so that same-second writes on coarse-mtime filesystems
    (FAT/exFAT, 1-2s resolution) still trigger a rebuild.
    """
    base = _output_base() / video_id
    chunks = base / "chunks.json"
    player = base / "player.json"
    if not chunks.exists() or not player.exists():
        return False
    return chunks.stat().st_mtime >= player.stat().st_mtime


def _stage_index(name: str) -> int:
    """Return the 0-based index of a stage name, or 0 if unrecognised."""
    try:
        return _STAGE_ORDER.index(name)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Top-level commands
# ---------------------------------------------------------------------------


@app.command()
def init() -> None:
    """プロジェクト初期化（output/ ディレクトリ確認、バージョン表示）。"""
    out = _output_base()
    out.mkdir(parents=True, exist_ok=True)
    typer.echo(f"yt-ja version {_VERSION}")
    typer.echo(f"output directory: {out.resolve()}")

    env_file = Path(".env")
    env_example = Path(".env.example")
    if not env_file.exists():
        if env_example.exists():
            shutil.copy(env_example, env_file)
            typer.echo(".env created from .env.example")
        else:
            typer.echo(".env not found (no .env.example to copy from)")
    else:
        typer.echo(".env found")


@app.command()
def process(
    url: str = typer.Argument(..., help="YouTube URL"),
    from_stage: Optional[str] = typer.Option(
        None,
        "--from",
        help="再開ステージ (例: normalize, chunk, translate, tts, sync)",
    ),
    stop_after: Optional[str] = typer.Option(
        None,
        "--stop-after",
        help="このステージで停止 (例: chunked, translated, tts_generated)",
    ),
    force_tts: bool = typer.Option(False, "--force-tts", help="TTS を強制再生成"),
    force_sync: bool = typer.Option(False, "--force-sync", help="同期JSONを強制再生成"),
    skip_metadata: bool = typer.Option(False, "--skip-metadata", help="メタデータ取得をスキップ"),
) -> None:
    """URL を受け取り全パイプラインを実行する（metadata→fetch→normalize→chunk→translate→narrate→tts→sync）。"""
    from pipeline.core.video_id import extract_video_id
    from pipeline.core.metadata import init_metadata, update_status
    from pipeline.core.subtitles import fetch_subtitle, NoSubtitleError
    from pipeline.core.normalize import normalize
    from pipeline.core.chunk import chunk as do_chunk
    from pipeline.models import ProcessingStatus

    video_id = extract_video_id(url)
    typer.echo(f"video_id: {video_id}")

    skip_before = _stage_index(from_stage) if from_stage else 0

    # Map stop_after shorthand to canonical stage names
    _stop_aliases = {
        "chunked": "chunk",
        "translated": "translate",
        "narration_script_created": "narrate",
        "tts_generated": "tts",
        "sync_generated": "sync",
        "completed": "completed",
    }
    stop_stage = None
    if stop_after:
        stop_stage = _stop_aliases.get(stop_after, stop_after)

    def _past_stop(current: str) -> bool:
        if stop_stage is None:
            return False
        ci = _stage_index(current)
        si = _stage_index(stop_stage)
        return ci > si

    # ---- Stage 0: metadata ----
    if skip_metadata or (skip_before > 0 and _output_exists(video_id, "metadata.json")):
        typer.echo("[skip] metadata (already exists or --skip-metadata)")
    else:
        typer.echo(">> metadata...")
        meta = init_metadata(url)
        typer.echo(f"   title: {meta.title}")

    if _past_stop("metadata"):
        typer.echo("stopped after: metadata")
        return

    # ---- Stage 1: fetch-subtitle ----
    if skip_before > 1 and _output_exists(video_id, "transcript.en.vtt"):
        typer.echo("[skip] fetch-subtitle (transcript.en.vtt exists)")
    else:
        typer.echo(">> fetch-subtitle...")
        try:
            vtt = fetch_subtitle(video_id)
            typer.echo(f"   saved: {vtt}")
            if _output_exists(video_id, "metadata.json"):
                update_status(video_id, ProcessingStatus.subtitle_fetched)
        except NoSubtitleError as exc:
            typer.echo(f"[error] {exc}", err=True)
            if _output_exists(video_id, "metadata.json"):
                update_status(video_id, ProcessingStatus.failed_no_subtitle)
            raise typer.Exit(1)

    if _past_stop("fetch-subtitle"):
        typer.echo("stopped after: fetch-subtitle")
        return

    # ---- Stage 2: normalize ----
    if skip_before > 2 and _output_exists(video_id, "transcript.normalized.json"):
        typer.echo("[skip] normalize (transcript.normalized.json exists)")
    else:
        typer.echo(">> normalize...")
        items = normalize(video_id)
        typer.echo(f"   {len(items)} transcript items")
        if _output_exists(video_id, "metadata.json"):
            update_status(video_id, ProcessingStatus.subtitle_normalized)

    if _past_stop("normalize"):
        typer.echo("stopped after: normalize")
        return

    # ---- Stage 3: chunk ----
    if skip_before > 3 and _output_exists(video_id, "chunks.json"):
        typer.echo("[skip] chunk (chunks.json exists)")
    else:
        typer.echo(">> chunk...")
        chunks = do_chunk(video_id)
        typer.echo(f"   {len(chunks)} chunks")
        if _output_exists(video_id, "metadata.json"):
            update_status(video_id, ProcessingStatus.chunked)

    if _past_stop("chunk"):
        typer.echo("stopped after: chunk")
        return

    # ---- Stage 4: translate ----
    backend = os.environ.get("EJUTUBE_LLM_BACKEND", "ollama").lower()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if backend == "anthropic" and not api_key:
        typer.echo(
            "[warn] EJUTUBE_LLM_BACKEND=anthropic but ANTHROPIC_API_KEY not set — "
            "skipping translate/narrate/tts/sync. Set ANTHROPIC_API_KEY or switch to "
            "EJUTUBE_LLM_BACKEND=ollama.",
            err=True,
        )
        _run_sync_if_possible(video_id, force_sync)
        return

    if skip_before > 4 and _translation_done(video_id):
        typer.echo("[skip] translate (chunks already have subtitle_ja)")
    else:
        typer.echo(">> translate...")
        from pipeline.translation import translate_chunks
        chunks_t = translate_chunks(video_id)
        typer.echo(f"   translated {len(chunks_t)} chunks")
        if _output_exists(video_id, "metadata.json"):
            update_status(video_id, ProcessingStatus.translated)

    if _past_stop("translate"):
        typer.echo("stopped after: translate")
        return

    # ---- Stage 5: narrate ----
    if skip_before > 5 and _narration_done(video_id):
        typer.echo("[skip] narrate (chunks already have narration_ja)")
    else:
        typer.echo(">> narrate...")
        from pipeline.translation import narrate_chunks
        chunks_n = narrate_chunks(video_id)
        typer.echo(f"   narrated {len(chunks_n)} chunks")
        if _output_exists(video_id, "metadata.json"):
            update_status(video_id, ProcessingStatus.narration_script_created)

    if _past_stop("narrate"):
        typer.echo("stopped after: narrate")
        return

    # ---- Stage 5.5: summarize + extract-commands (Bug C: spec §8.14/§8.15) ----
    # Best-effort: skip silently if already done; failures here don't block tts/sync.
    if not _output_exists(video_id, "summary.md"):
        typer.echo(">> summarize...")
        try:
            from pipeline.translation.summary import summarize
            summarize(video_id)
            typer.echo("   summary.md written")
        except Exception as exc:
            typer.echo(f"[warn] summarize failed (continuing): {exc}", err=True)
    else:
        typer.echo("[skip] summarize (summary.md exists)")

    if not _output_exists(video_id, "commands.md"):
        typer.echo(">> extract-commands...")
        try:
            from pipeline.translation.commands import extract_commands
            extract_commands(video_id)
            typer.echo("   commands.md written")
        except Exception as exc:
            typer.echo(f"[warn] extract-commands failed (continuing): {exc}", err=True)
    else:
        typer.echo("[skip] extract-commands (commands.md exists)")

    # ---- Stage 6: tts ----
    if skip_before > 6 and _output_exists(video_id, "narration_segments.json"):
        typer.echo("[skip] tts (narration_segments.json exists)")
    else:
        typer.echo(">> tts...")
        try:
            from pipeline.tts.synthesize import synthesize_all
            from pipeline.tts.quality import print_quality_warnings
            from pipeline.tts.voicevox import VoicevoxUnavailableError
            segments = synthesize_all(video_id=video_id, force=force_tts, preset_name=None)
            print_quality_warnings(segments)
            typer.echo(f"   {len(segments)} segment(s) written")
            if _output_exists(video_id, "metadata.json"):
                update_status(video_id, ProcessingStatus.tts_generated)
        except VoicevoxUnavailableError as exc:
            typer.echo(f"[warn] VOICEVOX unavailable: {exc}", err=True)
            typer.echo("[warn] Skipping tts+sync. See docs/VOICEVOX_SETUP.md.", err=True)
            if _output_exists(video_id, "metadata.json"):
                update_status(video_id, ProcessingStatus.narration_script_created)
            _run_sync_if_possible(video_id, force_sync)
            return

    if _past_stop("tts"):
        typer.echo("stopped after: tts")
        return

    # ---- Stage 7: sync / build-player ----
    _run_sync_if_possible(video_id, force_sync)


def _run_sync_if_possible(video_id: str, force: bool = False) -> None:
    from pipeline.models import ProcessingStatus

    player_path = _output_base() / video_id / "player.json"
    # Bug A fix: stale player.json gets refreshed when chunks.json is newer.
    stale = _chunks_newer_than_player(video_id)
    if not force and not stale and player_path.exists():
        typer.echo("[skip] sync (player.json exists)")
        return
    if stale and not force:
        typer.echo("[info] chunks.json newer than player.json — rebuilding")

    if not _output_exists(video_id, "chunks.json"):
        typer.echo("[skip] sync (chunks.json not found)")
        return

    typer.echo(">> sync (build-player)...")
    try:
        from pipeline.sync import build_player_json
        player = build_player_json(video_id)
        typer.echo(f"   {len(player.chunks)} chunks written to player.json")
        if _output_exists(video_id, "metadata.json"):
            update_status(video_id, ProcessingStatus.completed)
        typer.echo(
            f'Done. Run "yt-ja serve" to view at http://localhost:3000/play/{video_id}'
        )
    except Exception as exc:
        typer.echo(f"[error] sync failed: {exc}", err=True)


@app.command()
def serve(
    port: int = typer.Option(3000, "--port", help="ポート番号"),
) -> None:
    """ローカルWebサーバーを起動する（npm run dev in web/）。"""
    web_dir = Path(__file__).parent.parent / "web"
    if not web_dir.exists():
        typer.echo(f"[error] web/ directory not found: {web_dir}", err=True)
        raise typer.Exit(1)

    output_dir = (_output_base()).resolve()
    env = {**os.environ, "OUTPUT_DIR": str(output_dir)}

    typer.echo(f"http://localhost:{port}")
    typer.echo("Press Ctrl+C to stop.")

    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(web_dir),
        env=env,
        shell=True,
    )
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()


# ---------------------------------------------------------------------------
# Step-by-step commands
# ---------------------------------------------------------------------------


@app.command("fetch-subtitle")
def fetch_subtitle_cmd(
    video_id: str = typer.Argument(..., help="YouTube video_id"),
    file: Optional[Path] = typer.Option(
        None,
        "--file",
        "-f",
        help="ローカルのVTT/SRTファイルを指定してコピーする",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
) -> None:
    """英語字幕を取得して transcript.en.vtt に保存する。"""
    from pipeline.core.subtitles import fetch_subtitle, import_local_subtitle, NoSubtitleError

    if file is not None:
        dest = import_local_subtitle(video_id, file)
        typer.echo(f"imported: {dest}")
        return

    try:
        vtt = fetch_subtitle(video_id)
        typer.echo(f"saved: {vtt}")
    except NoSubtitleError as exc:
        typer.echo(f"[error] {exc}", err=True)
        raise typer.Exit(1)


@app.command()
def normalize(
    video_id: str = typer.Argument(..., help="YouTube video_id"),
) -> None:
    """VTT を transcript.normalized.json に変換する。"""
    from pipeline.core.normalize import normalize as do_normalize

    items = do_normalize(video_id)
    typer.echo(f"{len(items)} transcript items written to transcript.normalized.json")


@app.command()
def chunk(
    video_id: str = typer.Argument(..., help="YouTube video_id"),
    target: int = typer.Option(25, "--target", help="目標チャンク長（秒）"),
    max_s: int = typer.Option(30, "--max", help="最大チャンク長（秒）"),
) -> None:
    """正規化済み字幕を 10〜30 秒チャンクに分割して chunks.json を生成する。"""
    from pipeline.core.chunk import chunk as do_chunk

    chunks = do_chunk(video_id, target_seconds=target, max_seconds=max_s)
    typer.echo(f"{len(chunks)} chunks written to chunks.json")


@app.command()
def translate(
    video_id: str = typer.Argument(..., help="YouTube video_id"),
) -> None:
    """chunks.json に日本語字幕 (subtitle_ja) を追加する。"""
    from pipeline.translation import translate_chunks

    chunks = translate_chunks(video_id)
    typer.echo(f"translated {len(chunks)} chunks -> output/{video_id}/chunks.json")


@app.command()
def narrate(
    video_id: str = typer.Argument(..., help="YouTube video_id"),
    force: bool = typer.Option(False, "--force", help="既存の narration_ja を再生成する"),
) -> None:
    """chunks.json に読み上げ台本 (narration_ja) を追加する。"""
    import json as _json
    from pipeline.translation import narrate_chunks

    if force:
        # Clear narration_ja on every chunk so the stage re-runs end-to-end.
        path = _output_base() / video_id / "chunks.json"
        if path.exists():
            data = _json.loads(path.read_text(encoding="utf-8"))
            for c in data:
                c.pop("narration_ja", None)
            path.write_text(
                _json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    chunks = narrate_chunks(video_id)
    typer.echo(
        f"narrated {len(chunks)} chunks -> output/{video_id}/chunks.json + narration.script.md"
    )


@app.command()
def summarize(
    video_id: str = typer.Argument(..., help="YouTube video_id"),
) -> None:
    """要約とチャンク別要点を summary.md に書き出す。"""
    from pipeline.translation import summarize as _summarize

    path = _summarize(video_id)
    typer.echo(f"wrote {path}")


@app.command("extract-commands")
def extract_commands_cmd(
    video_id: str = typer.Argument(..., help="YouTube video_id"),
    force: bool = typer.Option(False, "--force", help="既存の commands.md を上書きする"),
) -> None:
    """transcript.normalized.json からコマンド・パスを抽出して commands.md に書き出す。"""
    from pipeline.translation import extract_commands

    out = _output_base() / video_id / "commands.md"
    if out.exists() and not force:
        typer.echo(f"[skip] commands.md exists at {out} (use --force to overwrite)")
        return

    path = extract_commands(video_id)
    typer.echo(f"wrote {path}")


@app.command()
def tts(
    video_id: str = typer.Argument(..., help="YouTube video_id"),
    voice: str = typer.Option("tsumugi", "--voice", help="Speaker preset name (tsumugi, zundamon, metan)"),
    speaker: Optional[int] = typer.Option(None, "--speaker", help="VOICEVOX speaker ID (overrides --voice)"),
    speed: Optional[float] = typer.Option(None, "--speed", help="Speed scale (overrides preset default)"),
    force: bool = typer.Option(False, "--force", help="Re-synthesize even if WAV already exists"),
) -> None:
    """VOICEVOX で TTS 音声を生成して audio/*.wav に保存する。

    --voice でプリセット名を指定（デフォルト: tsumugi = 春日部つむぎ）。
    --speaker で speaker ID を直接指定すると --voice より優先されます。
    """
    from pipeline.tts.synthesize import synthesize_all
    from pipeline.tts.quality import print_quality_warnings
    from pipeline.tts.presets import get_preset

    # Validate preset name early so the error is clear
    if speaker is None:
        try:
            get_preset(voice)
        except KeyError as exc:
            typer.echo(f"[error] {exc}", err=True)
            raise typer.Exit(1)

    segments = synthesize_all(
        video_id=video_id,
        speaker=speaker,
        speed_scale=speed,
        preset_name=voice if speaker is None else None,
        force=force,
    )
    print_quality_warnings(segments)
    typer.echo(f"TTS complete: {len(segments)} segment(s) written.")


@app.command("tts-speakers")
def tts_speakers() -> None:
    """利用可能な VOICEVOX 話者一覧を表示する（プリセット + 全話者）。"""
    import asyncio
    from pipeline.tts.voicevox import VoicevoxClient
    from pipeline.tts.presets import list_presets, DEFAULT_PRESET

    typer.echo("=== Presets ===")
    for preset in list_presets():
        marker = " *" if preset.name == DEFAULT_PRESET else ""
        typer.echo(
            f"  {preset.name:<10}  {preset.display_name}  "
            f"(id={preset.speaker_id}, style={preset.style}, speed={preset.speed_scale}){marker}"
        )
    typer.echo("  (* = default)")
    typer.echo("")

    async def _list() -> None:
        client = VoicevoxClient()
        speakers = await client.list_speakers()
        typer.echo("=== All VOICEVOX speakers ===")
        for sp in speakers:
            styles = ", ".join(
                f"{s['name']} (id={s['id']})" for s in sp.get("styles", [])
            )
            typer.echo(f"{sp['name']}: {styles}")

    asyncio.run(_list())


@app.command()
def sync(
    video_id: str = typer.Argument(..., help="YouTube video_id"),
) -> None:
    """chunks.json + narration_segments.json を結合して player.json を生成する。"""
    from pipeline.sync import build_player_json

    player = build_player_json(video_id)
    typer.echo(f"{len(player.chunks)} chunks written to output/{video_id}/player.json")
    typer.echo(f'Run "yt-ja serve" to view at http://localhost:3000/play/{video_id}')


@app.command("build-player")
def build_player(
    video_id: str = typer.Argument(..., help="YouTube video_id"),
) -> None:
    """player.json を組み立てる（sync のエイリアス）。"""
    from pipeline.sync import build_player_json

    player = build_player_json(video_id)
    typer.echo(f"{len(player.chunks)} chunks written to output/{video_id}/player.json")
    typer.echo(f'Run "yt-ja serve" to view at http://localhost:3000/play/{video_id}')


if __name__ == "__main__":
    app()
