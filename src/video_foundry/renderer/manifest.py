from __future__ import annotations

from pathlib import Path

from video_foundry.shared.schemas import RenderKeyframe, RenderManifest, utc_now
from video_foundry.shared.storage import ProjectStorage


RENDER_MANIFEST_PATH = "renders/render-manifest.json"


def build_render_manifest(
    *,
    project_id: str,
    format_name: str,
    fps: int,
    width: int,
    height: int,
    duration_sec: float,
    source_image_path: str,
    source_image_sha256: str,
    storyboard_version: int,
    subtitles_path: str,
    credit_text: str,
    subtitle_overlay: dict[str, float | str],
    credit_overlay: dict[str, float | str],
    preview_output_path: str | None,
    final_output_path: str | None,
    frame_count: int,
    keyframes: list[RenderKeyframe],
) -> RenderManifest:
    return RenderManifest(
        project_id=project_id,
        format=format_name,
        fps=fps,
        width=width,
        height=height,
        duration_sec=duration_sec,
        source_image_path=source_image_path,
        source_image_sha256=source_image_sha256,
        storyboard_version=storyboard_version,
        subtitles_path=subtitles_path,
        credit_text=credit_text,
        credit_overlay=credit_overlay,
        subtitle_overlay=subtitle_overlay,
        preview_output_path=preview_output_path,
        final_output_path=final_output_path,
        frame_count=frame_count,
        keyframes=keyframes,
        deterministic_rules=[
            "Source image pixels are only cropped, resized, and overlaid.",
            "No generative image, video, interpolation, repainting, or super-resolution model is used.",
            "Crop motion is derived from approved storyboard crop_start/crop_end and easing.",
        ],
        updated_at=utc_now(),
    )


def write_render_manifest(storage: ProjectStorage, project_id: str, manifest: RenderManifest) -> Path:
    return storage.write_json(project_id, RENDER_MANIFEST_PATH, manifest)

