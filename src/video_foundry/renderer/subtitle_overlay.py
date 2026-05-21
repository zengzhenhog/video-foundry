from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from video_foundry.shared.schemas import SubtitleCue


@dataclass(frozen=True)
class OverlayBox:
    x: int
    y: int
    width: int
    height: int

    def as_manifest(self) -> dict[str, float | str]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "units": "px",
        }


def draw_text_overlays(
    image: Image.Image,
    *,
    time_sec: float,
    cues: list[SubtitleCue],
    credit_text: str,
    safe_area: dict[str, float],
) -> tuple[dict[str, float | str], dict[str, float | str]]:
    draw = ImageDraw.Draw(image, "RGBA")
    font = _load_font(size=max(20, image.height // 42))
    small_font = _load_font(size=max(16, image.height // 64))
    subtitle_box = _subtitle_box(image.size, safe_area)
    credit_box = _credit_box(image.size, safe_area)

    cue = _active_cue(cues, time_sec)
    if cue and cue.text.strip():
        text = _wrap_text(cue.text.strip(), font, subtitle_box.width - 32)
        _draw_boxed_text(draw, subtitle_box, text, font, anchor="center")

    if credit_text.strip():
        credit = _wrap_text(f"Credit: {credit_text.strip()}", small_font, credit_box.width - 20, max_lines=2)
        _draw_boxed_text(draw, credit_box, credit, small_font, anchor="left")

    return subtitle_box.as_manifest(), credit_box.as_manifest()


def _active_cue(cues: list[SubtitleCue], time_sec: float) -> SubtitleCue | None:
    for cue in cues:
        if cue.start_sec <= time_sec < cue.end_sec:
            return cue
    return cues[-1] if cues and time_sec >= cues[-1].end_sec else None


def _subtitle_box(size: tuple[int, int], safe_area: dict[str, float]) -> OverlayBox:
    width, height = size
    left = int(width * safe_area.get("left", 0.06))
    right = int(width * safe_area.get("right", 0.06))
    bottom = int(height * safe_area.get("bottom", 0.12))
    box_height = max(90, height // 8)
    return OverlayBox(
        x=left,
        y=max(0, height - bottom - box_height),
        width=max(1, width - left - right),
        height=box_height,
    )


def _credit_box(size: tuple[int, int], safe_area: dict[str, float]) -> OverlayBox:
    width, height = size
    left = int(width * safe_area.get("left", 0.06))
    top = int(height * safe_area.get("top", 0.08))
    right = int(width * safe_area.get("right", 0.06))
    return OverlayBox(
        x=left,
        y=top,
        width=max(1, width - left - right),
        height=max(56, height // 18),
    )


def _draw_boxed_text(
    draw: ImageDraw.ImageDraw,
    box: OverlayBox,
    text: str,
    font: ImageFont.ImageFont,
    *,
    anchor: str,
) -> None:
    draw.rounded_rectangle(
        (box.x, box.y, box.x + box.width, box.y + box.height),
        radius=10,
        fill=(0, 0, 0, 132),
    )
    text_bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=6)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    if anchor == "center":
        x = box.x + max(12, (box.width - text_width) // 2)
        y = box.y + max(8, (box.height - text_height) // 2)
    else:
        x = box.x + 10
        y = box.y + max(8, (box.height - text_height) // 2)
    draw.multiline_text((x, y), text, font=font, fill=(255, 255, 255, 238), spacing=6)


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, *, max_lines: int = 3) -> str:
    words = text.split()
    if not words:
        return ""
    lines: list[str] = []
    current = words[0]
    probe = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(probe)
    for word in words[1:]:
        candidate = f"{current} {word}"
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines - 1:
                break
    if len(lines) < max_lines:
        lines.append(current)
    return "\n".join(lines[:max_lines])


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size=size)
    except OSError:
        return ImageFont.load_default()

