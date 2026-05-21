from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from video_foundry.renderer.crops import CropRect, interpolate_crop
from video_foundry.renderer.subtitle_overlay import draw_text_overlays
from video_foundry.shared.schemas import RenderKeyframe, Storyboard, StoryboardShot, SubtitleCue


@dataclass(frozen=True)
class RenderPresetSize:
    width: int
    height: int


@dataclass(frozen=True)
class FrameRenderResult:
    frame_paths: list[Path]
    keyframes: list[RenderKeyframe]
    subtitle_overlay: dict[str, float | str]
    credit_overlay: dict[str, float | str]


def render_storyboard_frames(
    *,
    project_id: str,
    image_path: Path,
    frames_dir: Path,
    relative_frames_dir: str,
    storyboard: Storyboard,
    output_size: RenderPresetSize,
    cues: list[SubtitleCue],
    credit_text: str,
    duration_limit_sec: float | None = None,
) -> FrameRenderResult:
    frames_dir.mkdir(parents=True, exist_ok=True)
    _clear_existing_frames(frames_dir)
    duration_sec = min(storyboard.duration_sec, duration_limit_sec) if duration_limit_sec else storyboard.duration_sec
    frame_count = max(1, math.ceil(duration_sec * storyboard.fps))
    frame_paths: list[Path] = []
    keyframes: list[RenderKeyframe] = []
    subtitle_overlay: dict[str, float | str] = {}
    credit_overlay: dict[str, float | str] = {}

    with Image.open(image_path) as opened:
        source = ImageOps.exif_transpose(opened).convert("RGB")
        for frame_index in range(frame_count):
            time_sec = min(frame_index / storyboard.fps, max(0.0, duration_sec - 0.001))
            shot = _shot_at_time(storyboard.shots, time_sec)
            crop = crop_for_shot(shot, time_sec)
            frame = _crop_and_resize(source, crop, output_size)
            subtitle_overlay, credit_overlay = draw_text_overlays(
                frame,
                time_sec=time_sec,
                cues=cues,
                credit_text=credit_text,
                safe_area=storyboard.safe_area,
            )
            frame_path = frames_dir / f"frame_{frame_index:06d}.png"
            frame.save(frame_path, format="PNG")
            frame_paths.append(frame_path)
            if _is_keyframe(frame_index, frame_count, shot, keyframes):
                keyframes.append(
                    RenderKeyframe(
                        shot_id=shot.id,
                        frame_index=frame_index,
                        time_sec=round(time_sec, 3),
                        crop=crop,
                        output_path=f"{relative_frames_dir}/frame_{frame_index:06d}.png",
                    )
                )

    return FrameRenderResult(
        frame_paths=frame_paths,
        keyframes=keyframes,
        subtitle_overlay=subtitle_overlay,
        credit_overlay=credit_overlay,
    )


def crop_for_shot(shot: StoryboardShot, time_sec: float) -> CropRect:
    duration = max(shot.end_sec - shot.start_sec, 0.001)
    progress = (time_sec - shot.start_sec) / duration
    return interpolate_crop(shot.crop_start, shot.crop_end, progress, shot.easing)


def _shot_at_time(shots: list[StoryboardShot], time_sec: float) -> StoryboardShot:
    for shot in shots:
        if shot.start_sec <= time_sec < shot.end_sec:
            return shot
    return shots[-1]


def _crop_and_resize(source: Image.Image, crop: CropRect, output_size: RenderPresetSize) -> Image.Image:
    width, height = source.size
    x1, y1, x2, y2 = crop
    left = max(0, min(width - 1, round(x1 * width)))
    top = max(0, min(height - 1, round(y1 * height)))
    right = max(left + 1, min(width, round(x2 * width)))
    bottom = max(top + 1, min(height, round(y2 * height)))
    cropped = source.crop((left, top, right, bottom))
    return cropped.resize((output_size.width, output_size.height), Image.Resampling.LANCZOS)


def _is_keyframe(
    frame_index: int,
    frame_count: int,
    shot: StoryboardShot,
    keyframes: list[RenderKeyframe],
) -> bool:
    if frame_index in {0, frame_count - 1}:
        return True
    return not any(keyframe.shot_id == shot.id for keyframe in keyframes)


def _clear_existing_frames(frames_dir: Path) -> None:
    for candidate in frames_dir.glob("frame_*.png"):
        if candidate.is_file():
            candidate.unlink()

