"""
Speaker presets for VOICEVOX TTS.

IDs verified against VOICEVOX v0.25.0 running at http://127.0.0.1:50021.
"""

from __future__ import annotations

from typing import NamedTuple


class SpeakerPreset(NamedTuple):
    name: str           # internal key, e.g. "tsumugi"
    display_name: str   # 春日部つむぎ
    speaker_id: int
    style: str          # ノーマル
    speed_scale: float  # per-speaker tuning


PRESETS: dict[str, SpeakerPreset] = {
    "tsumugi": SpeakerPreset("tsumugi", "春日部つむぎ", 8,  "ノーマル", 1.1),
    "zundamon": SpeakerPreset("zundamon", "ずんだもん",  3,  "ノーマル", 1.1),
    "metan":    SpeakerPreset("metan",    "四国めたん",  2,  "ノーマル", 1.1),
}

DEFAULT_PRESET = "tsumugi"   # 春日部つむぎ — 聞きやすい


def get_preset(key: str) -> SpeakerPreset:
    """Return the preset for *key*.

    Raises KeyError if the key is not found.
    """
    if key not in PRESETS:
        raise KeyError(
            f"Unknown preset {key!r}. Valid presets: {', '.join(PRESETS)}"
        )
    return PRESETS[key]


def get_default() -> SpeakerPreset:
    """Return the default speaker preset (春日部つむぎ)."""
    return PRESETS[DEFAULT_PRESET]


def list_presets() -> list[SpeakerPreset]:
    """Return all presets in insertion order."""
    return list(PRESETS.values())
