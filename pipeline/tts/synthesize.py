"""
Batch TTS synthesis: reads chunks.json, calls VOICEVOX, writes audio/*.wav,
measures durations, and writes narration_segments.json.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from pydantic import ValidationError

from pipeline.core.paths import get_video_output_dir
from pipeline.models import Chunk, NarrationSegment
from pipeline.tts.duration import measure_wav_duration
from pipeline.tts.voicevox import VoicevoxClient


def _audio_dir(video_id: str) -> Path:
    return get_video_output_dir(video_id) / "audio"


def _segments_path(video_id: str) -> Path:
    return get_video_output_dir(video_id) / "narration_segments.json"


def _chunks_path(video_id: str) -> Path:
    return get_video_output_dir(video_id) / "chunks.json"


def _load_existing_segments(video_id: str) -> dict[int, NarrationSegment]:
    path = _segments_path(video_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {seg["chunk_id"]: NarrationSegment.model_validate(seg) for seg in data}
    except (json.JSONDecodeError, OSError, KeyError, ValidationError):
        return {}


# Auto-fit constants (Issue F).
# If audio overflows target by >10%, re-synthesize at a higher speed to fit.
_OVERFLOW_SLACK = 1.10        # 10% slack before triggering re-synth
_AIM_UNDER = 1.05             # aim slightly under target on retry
_MAX_SPEED_SCALE = 1.5        # faster than this becomes unintelligible
_RESYNTH_MIN_DELTA = 0.01     # don't re-synth for a negligible speed bump


async def _synth_at_speed(
    client: VoicevoxClient,
    text: str,
    speaker: int,
    speed_scale: float,
    wav_path: Path,
) -> float:
    """Synthesize *text* at *speed_scale*, write WAV, return measured duration."""
    query = await client.audio_query(
        text=text,
        speaker=speaker,
        speed_scale=speed_scale,
    )
    wav_bytes = await client.synthesize(query=query, speaker=speaker)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path.write_bytes(wav_bytes)
    return measure_wav_duration(wav_path)


async def _synth_one(
    client: VoicevoxClient,
    chunk: Chunk,
    video_id: str,
    speaker: int,
    speed_scale: float,
    sem: asyncio.Semaphore,
    force: bool,
    existing: dict[int, NarrationSegment],
) -> NarrationSegment:
    audio_file_rel = f"audio/{chunk.chunk_id:04d}.wav"
    wav_path = get_video_output_dir(video_id) / audio_file_rel

    target_duration = chunk.end - chunk.start

    # Idempotency check
    if not force and wav_path.exists() and chunk.chunk_id in existing:
        existing_seg = existing[chunk.chunk_id]
        measured = measure_wav_duration(wav_path)
        if abs(measured - existing_seg.audio_duration) < 0.05:
            return existing_seg

    async with sem:
        final_speed = speed_scale
        audio_duration = await _synth_at_speed(
            client=client,
            text=chunk.narration_ja,
            speaker=speaker,
            speed_scale=final_speed,
            wav_path=wav_path,
        )

        # Issue F: auto-fit if audio overflows target by >10%.
        if target_duration > 0 and audio_duration > target_duration * _OVERFLOW_SLACK:
            ratio = audio_duration / (target_duration * _AIM_UNDER)
            new_speed = min(_MAX_SPEED_SCALE, final_speed * ratio)
            if new_speed > final_speed + _RESYNTH_MIN_DELTA:
                print(
                    f"[tts] chunk {chunk.chunk_id}: overflow "
                    f"{audio_duration:.2f}s > target {target_duration:.2f}s — "
                    f"re-synth at speed_scale={new_speed:.3f} (was {final_speed:.3f})"
                )
                try:
                    audio_duration = await _synth_at_speed(
                        client=client,
                        text=chunk.narration_ja,
                        speaker=speaker,
                        speed_scale=new_speed,
                        wav_path=wav_path,
                    )
                    final_speed = new_speed
                except Exception as exc:
                    # Retry failed — keep the initial synth (wav_path still holds
                    # the first render) and continue the pipeline without crashing.
                    print(
                        f"[tts] chunk {chunk.chunk_id}: retry failed ({exc}) "
                        f"— keeping initial synth"
                    )

    return NarrationSegment(
        chunk_id=chunk.chunk_id,
        video_start=chunk.start,
        video_end=chunk.end,
        target_duration=target_duration,
        audio_duration=audio_duration,
        duration_diff=audio_duration - target_duration,
        audio_file=audio_file_rel,
    )


async def _synthesize_all_async(
    video_id: str,
    speaker: int,
    speed_scale: float,
    concurrency: int,
    force: bool,
) -> list[NarrationSegment]:
    chunks_path = _chunks_path(video_id)
    if not chunks_path.exists():
        raise FileNotFoundError(f"chunks.json not found: {chunks_path}")

    raw = json.loads(chunks_path.read_text(encoding="utf-8"))
    all_chunks = [Chunk.model_validate(c) for c in raw]
    chunks = [c for c in all_chunks if c.narration_ja]

    if not chunks:
        raise ValueError(f"No chunks with narration_ja found in {chunks_path}")

    existing = _load_existing_segments(video_id)
    client = VoicevoxClient()
    sem = asyncio.Semaphore(concurrency)

    segments: list[NarrationSegment] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task(f"Synthesizing {video_id}", total=len(chunks))

        async def run_one(chunk: Chunk) -> NarrationSegment:
            seg = await _synth_one(
                client=client,
                chunk=chunk,
                video_id=video_id,
                speaker=speaker,
                speed_scale=speed_scale,
                sem=sem,
                force=force,
                existing=existing,
            )
            progress.advance(task)
            return seg

        tasks = [run_one(c) for c in chunks]
        segments = list(await asyncio.gather(*tasks))

    segments.sort(key=lambda s: s.chunk_id)

    segments_path = _segments_path(video_id)
    segments_path.parent.mkdir(parents=True, exist_ok=True)
    segments_path.write_text(
        json.dumps([s.model_dump() for s in segments], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return segments


def synthesize_all(
    video_id: str,
    speaker: int | None = None,
    speed_scale: float | None = None,
    concurrency: int = 3,
    force: bool = False,
    preset_name: str | None = None,
) -> list[NarrationSegment]:
    """Synthesize TTS for all narrated chunks.

    Resolution order for speaker/speed_scale:
    1. Explicit *speaker* / *speed_scale* arguments (power-user override).
    2. *preset_name* lookup via :mod:`pipeline.tts.presets`.
    3. Default preset (春日部つむぎ).
    """
    from pipeline.tts.presets import get_default, get_preset

    if speaker is None or speed_scale is None:
        if preset_name is not None:
            preset = get_preset(preset_name)
        else:
            preset = get_default()
        if speaker is None:
            speaker = preset.speaker_id
        if speed_scale is None:
            speed_scale = preset.speed_scale

    return asyncio.run(
        _synthesize_all_async(
            video_id=video_id,
            speaker=speaker,
            speed_scale=speed_scale,
            concurrency=concurrency,
            force=force,
        )
    )
