from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from video_foundry.shared.schemas import BackgroundMusic


@dataclass(frozen=True)
class AudioMixPlan:
    narration_path: Path
    background_music_path: Path | None
    duration_sec: float
    background_volume_gain_db: float
    loop_background: bool
    fade_in_sec: float
    fade_out_sec: float

    @property
    def has_background_music(self) -> bool:
        return self.background_music_path is not None


def build_audio_mix_plan(
    *,
    narration_path: Path,
    duration_sec: float,
    background_music: BackgroundMusic | None = None,
    background_music_path: Path | None = None,
) -> AudioMixPlan:
    if background_music is None or background_music_path is None:
        return AudioMixPlan(
            narration_path=narration_path,
            background_music_path=None,
            duration_sec=duration_sec,
            background_volume_gain_db=-18.0,
            loop_background=False,
            fade_in_sec=0.0,
            fade_out_sec=0.0,
        )

    return AudioMixPlan(
        narration_path=narration_path,
        background_music_path=background_music_path,
        duration_sec=duration_sec,
        background_volume_gain_db=background_music.volume_gain_db,
        loop_background=background_music.loop,
        fade_in_sec=background_music.fade_in_sec,
        fade_out_sec=background_music.fade_out_sec,
    )

