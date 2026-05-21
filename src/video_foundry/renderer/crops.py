from __future__ import annotations

from typing import Literal


CropRect = tuple[float, float, float, float]
EasingName = Literal["linear", "ease_in", "ease_out", "ease_in_out"]


def interpolate_crop(
    crop_start: CropRect,
    crop_end: CropRect,
    progress: float,
    easing: str = "linear",
) -> CropRect:
    eased = easing_value(progress, easing)
    return tuple(
        round(start + (end - start) * eased, 6)
        for start, end in zip(crop_start, crop_end, strict=True)
    )  # type: ignore[return-value]


def easing_value(progress: float, easing: str = "linear") -> float:
    value = min(1.0, max(0.0, progress))
    if easing == "ease_in":
        return value * value
    if easing == "ease_out":
        return 1 - (1 - value) * (1 - value)
    if easing == "ease_in_out":
        if value < 0.5:
            return 2 * value * value
        return 1 - pow(-2 * value + 2, 2) / 2
    return value

