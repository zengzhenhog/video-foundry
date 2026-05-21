from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from video_foundry.shared.errors import AppError
from video_foundry.shared.schemas import Storyboard, StoryboardShot


TIMELINE_TOLERANCE_SEC = 0.01
MIN_CROP_WIDTH = 0.2
MIN_CROP_HEIGHT = 0.2


@dataclass(frozen=True)
class RenderPreset:
    format: str
    width: int
    height: int
    fps: int
    safe_area: dict[str, float]
    max_zoom: float


def load_render_preset(config_dir: Path, format_name: str) -> RenderPreset:
    presets = _load_render_presets(config_dir)
    raw_preset = presets.get(format_name)
    if not isinstance(raw_preset, dict):
        raise AppError(
            code="render_preset_missing",
            message="Render preset for the selected storyboard format was not found.",
            status_code=500,
            step="storyboard_validation",
            retryable=False,
            suggested_correction="Add the missing render preset before generating storyboard.",
            details={"format": format_name},
        )

    try:
        width = int(raw_preset["width"])
        height = int(raw_preset["height"])
        fps = int(raw_preset.get("fps", 30))
        max_zoom = float(raw_preset["max_zoom"])
        safe_area_px = raw_preset.get("safe_area", {})
        if not isinstance(safe_area_px, dict):
            raise TypeError("safe_area must be an object")
        safe_area = {
            "top": float(safe_area_px.get("top", 0)) / height,
            "right": float(safe_area_px.get("right", 0)) / width,
            "bottom": float(safe_area_px.get("bottom", 0)) / height,
            "left": float(safe_area_px.get("left", 0)) / width,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError(
            code="render_preset_invalid",
            message="Render preset contains invalid storyboard settings.",
            status_code=500,
            step="storyboard_validation",
            retryable=False,
            suggested_correction="Fix config/render-presets.json.",
            details={"format": format_name},
        ) from exc

    if width <= 0 or height <= 0 or fps <= 0 or max_zoom < 1:
        raise AppError(
            code="render_preset_invalid",
            message="Render preset dimensions, fps, and max_zoom must be positive.",
            status_code=500,
            step="storyboard_validation",
            retryable=False,
            suggested_correction="Fix config/render-presets.json.",
            details={"format": format_name},
        )

    return RenderPreset(
        format=format_name,
        width=width,
        height=height,
        fps=fps,
        safe_area=safe_area,
        max_zoom=max_zoom,
    )


def validate_storyboard(
    storyboard: Storyboard,
    *,
    max_zoom: float,
    min_crop_width: float = MIN_CROP_WIDTH,
    min_crop_height: float = MIN_CROP_HEIGHT,
    tolerance_sec: float = TIMELINE_TOLERANCE_SEC,
) -> None:
    if not storyboard.shots:
        _raise_storyboard_error(
            "storyboard_shots_required",
            "Storyboard must contain at least one shot.",
            details={"project_id": storyboard.project_id},
        )

    expected_start = 0.0
    for index, shot in enumerate(storyboard.shots, start=1):
        if abs(shot.start_sec - expected_start) > tolerance_sec:
            _raise_storyboard_error(
                "storyboard_timeline_invalid",
                "Storyboard shots must be continuous from 0 seconds.",
                details={
                    "shot_id": shot.id,
                    "index": index,
                    "expected_start_sec": expected_start,
                    "actual_start_sec": shot.start_sec,
                },
            )
        if shot.end_sec <= shot.start_sec:
            _raise_storyboard_error(
                "storyboard_timeline_invalid",
                "Shot end_sec must be greater than start_sec.",
                details={"shot_id": shot.id, "start_sec": shot.start_sec, "end_sec": shot.end_sec},
            )

        _validate_crop_rect(shot, field_name="crop_start", max_zoom=max_zoom)
        _validate_crop_rect(shot, field_name="crop_end", max_zoom=max_zoom)
        expected_start = shot.end_sec

    if abs(storyboard.duration_sec - expected_start) > tolerance_sec:
        _raise_storyboard_error(
            "storyboard_timeline_invalid",
            "Storyboard duration must match the end time of the last shot.",
            details={"duration_sec": storyboard.duration_sec, "last_end_sec": expected_start},
        )


def _validate_crop_rect(
    shot: StoryboardShot,
    *,
    field_name: str,
    max_zoom: float,
    min_crop_width: float = MIN_CROP_WIDTH,
    min_crop_height: float = MIN_CROP_HEIGHT,
) -> None:
    rect = getattr(shot, field_name)
    if len(rect) != 4:
        _raise_storyboard_error(
            "storyboard_crop_invalid",
            "Crop rectangles must contain exactly four coordinates.",
            details={"shot_id": shot.id, "field": field_name},
        )

    x1, y1, x2, y2 = rect
    if any(coordinate < 0 or coordinate > 1 for coordinate in rect):
        _raise_storyboard_error(
            "storyboard_crop_invalid",
            "Crop coordinates must be within [0, 1].",
            details={"shot_id": shot.id, "field": field_name, "crop": list(rect)},
        )

    width = x2 - x1
    height = y2 - y1
    if width <= min_crop_width or height <= min_crop_height:
        _raise_storyboard_error(
            "storyboard_crop_invalid",
            "Crop width and height must be greater than the minimum threshold.",
            details={
                "shot_id": shot.id,
                "field": field_name,
                "width": width,
                "height": height,
                "min_width": min_crop_width,
                "min_height": min_crop_height,
            },
        )

    zoom = max(1 / width, 1 / height)
    if zoom > max_zoom:
        _raise_storyboard_error(
            "storyboard_zoom_exceeded",
            "Crop zoom exceeds the selected render preset limit.",
            details={
                "shot_id": shot.id,
                "field": field_name,
                "zoom": zoom,
                "max_zoom": max_zoom,
            },
        )


def _load_render_presets(config_dir: Path) -> dict[str, Any]:
    preset_path = config_dir / "render-presets.json"
    try:
        data = json.loads(preset_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AppError(
            code="render_presets_missing",
            message="Render preset configuration was not found.",
            status_code=500,
            step="storyboard_validation",
            retryable=False,
            suggested_correction="Restore config/render-presets.json.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise AppError(
            code="render_presets_invalid",
            message="Render preset configuration is invalid JSON.",
            status_code=500,
            step="storyboard_validation",
            retryable=False,
            suggested_correction="Fix config/render-presets.json.",
        ) from exc
    if not isinstance(data, dict):
        raise AppError(
            code="render_presets_invalid",
            message="Render preset configuration must contain an object.",
            status_code=500,
            step="storyboard_validation",
            retryable=False,
            suggested_correction="Fix config/render-presets.json.",
        )
    return data


def _raise_storyboard_error(code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
    raise AppError(
        code=code,
        message=message,
        status_code=422,
        step="storyboard_validation",
        retryable=True,
        suggested_correction="Adjust shot timing and crop values before saving or approving.",
        details=details or {},
    )

