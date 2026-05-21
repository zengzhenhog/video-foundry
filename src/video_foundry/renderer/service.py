from __future__ import annotations

from pathlib import Path
from typing import Literal

from video_foundry.ai.script_generator import ensure_script_approved
from video_foundry.audio.background_music import read_background_music_metadata
from video_foundry.audio.mixer import build_audio_mix_plan
from video_foundry.ffmpeg.assembler import assemble_video
from video_foundry.renderer.frame_renderer import RenderPresetSize, render_storyboard_frames
from video_foundry.renderer.manifest import build_render_manifest, write_render_manifest
from video_foundry.shared.errors import AppError
from video_foundry.shared.paths import PROJECT_METADATA_FILE
from video_foundry.shared.schemas import Asset, Project, ProjectStatus, RenderManifest, Storyboard, SubtitlesManifest, VoiceConfig, utc_now
from video_foundry.shared.storage import ProjectStorage
from video_foundry.sources.upload_importer import read_asset_metadata
from video_foundry.storyboard.planner import read_project_storyboard
from video_foundry.storyboard.validator import load_render_preset
from video_foundry.subtitles.generator import read_subtitles_manifest
from video_foundry.voice.provider_registry import read_voice_config


PREVIEW_DURATION_SEC = 5.0
FRAMES_RELATIVE_DIR = "renders/frames"
PREVIEW_OUTPUT_TEMPLATE = "renders/preview_{format}.mp4"
FINAL_OUTPUT_TEMPLATE = "exports/final_{format}.mp4"


RenderMode = Literal["preview", "final"]


def render_project_preview(
    storage: ProjectStorage,
    project_id: str,
    *,
    config_dir: Path,
) -> RenderManifest:
    return _render_project_video(storage, project_id, config_dir=config_dir, mode="preview")


def export_project_video(
    storage: ProjectStorage,
    project_id: str,
    *,
    config_dir: Path,
) -> RenderManifest:
    return _render_project_video(storage, project_id, config_dir=config_dir, mode="final")


def _render_project_video(
    storage: ProjectStorage,
    project_id: str,
    *,
    config_dir: Path,
    mode: RenderMode,
) -> RenderManifest:
    project = storage.read_project(project_id)
    ensure_script_approved(storage, project.id, step="render_validation")
    asset = _required_asset(storage, project)
    storyboard = _required_storyboard(storage, project)
    subtitles = _required_subtitles(storage, project, storyboard)
    voice_config = _required_voice(storage, project)
    preset = load_render_preset(config_dir, storyboard.format)

    duration_limit = PREVIEW_DURATION_SEC if mode == "preview" else None
    render_duration = min(storyboard.duration_sec, duration_limit) if duration_limit else storyboard.duration_sec
    source_image_path = storage.resolve_project_path(project.id, asset.image_original_path or "")
    frames_dir = storage.resolve_project_path(project.id, FRAMES_RELATIVE_DIR)
    output_relative_path = (
        PREVIEW_OUTPUT_TEMPLATE.format(format=storyboard.format)
        if mode == "preview"
        else FINAL_OUTPUT_TEMPLATE.format(format=storyboard.format)
    )
    output_path = storage.resolve_project_path(project.id, output_relative_path)

    frame_result = render_storyboard_frames(
        project_id=project.id,
        image_path=source_image_path,
        frames_dir=frames_dir,
        relative_frames_dir=FRAMES_RELATIVE_DIR,
        storyboard=storyboard,
        output_size=RenderPresetSize(width=preset.width, height=preset.height),
        cues=subtitles.cues,
        credit_text=asset.credit,
        duration_limit_sec=duration_limit,
    )

    background_music = read_background_music_metadata(storage, project.id)
    background_music_path = (
        storage.resolve_project_path(project.id, background_music.file_path)
        if background_music and storage.project_file_exists(project.id, background_music.file_path)
        else None
    )
    audio_mix = build_audio_mix_plan(
        narration_path=storage.resolve_project_path(project.id, voice_config.audio_path or ""),
        duration_sec=render_duration,
        background_music=background_music,
        background_music_path=background_music_path,
    )
    assemble_video(
        frames_dir=frames_dir,
        fps=storyboard.fps,
        duration_sec=render_duration,
        output_path=output_path,
        audio_mix=audio_mix,
    )

    manifest = build_render_manifest(
        project_id=project.id,
        format_name=storyboard.format,
        fps=storyboard.fps,
        width=preset.width,
        height=preset.height,
        duration_sec=render_duration,
        source_image_path=asset.image_original_path or "",
        source_image_sha256=asset.sha256 or "",
        storyboard_version=storyboard.version,
        subtitles_path=subtitles.srt_path,
        credit_text=asset.credit,
        subtitle_overlay=frame_result.subtitle_overlay,
        credit_overlay=frame_result.credit_overlay,
        preview_output_path=output_relative_path if mode == "preview" else None,
        final_output_path=output_relative_path if mode == "final" else None,
        frame_count=len(frame_result.frame_paths),
        keyframes=frame_result.keyframes,
    )
    write_render_manifest(storage, project.id, manifest)
    _refresh_project_after_render(storage, project, mode=mode)
    return manifest


def _required_asset(storage: ProjectStorage, project: Project) -> Asset:
    asset = read_asset_metadata(storage, project.id)
    if asset is None or not asset.image_original_path or not storage.project_file_exists(project.id, asset.image_original_path):
        _raise_missing_input("render_source_image_missing", "A source image is required before rendering.", "assets")
    if not asset.credit.strip():
        _raise_missing_input("missing_credit", "Credit is required before rendering.", "assets")
    if not asset.sha256:
        _raise_missing_input("render_source_hash_missing", "Source image hash is required before rendering.", "assets")
    return asset


def _required_storyboard(storage: ProjectStorage, project: Project) -> Storyboard:
    storyboard = read_project_storyboard(storage, project.id)
    if not storyboard.approved or project.stale_artifacts.get("storyboard"):
        _raise_missing_input(
            "storyboard_not_approved",
            "Storyboard must be approved and current before rendering.",
            "storyboard_review",
        )
    return storyboard


def _required_subtitles(
    storage: ProjectStorage,
    project: Project,
    storyboard: Storyboard,
) -> SubtitlesManifest:
    subtitles = read_subtitles_manifest(storage, project.id)
    srt_exists = storage.project_file_exists(project.id, subtitles.srt_path)
    vtt_exists = storage.project_file_exists(project.id, subtitles.vtt_path)
    if subtitles.stale or project.stale_artifacts.get("subtitles") or not srt_exists or not vtt_exists:
        _raise_missing_input("subtitles_stale_or_missing", "Current subtitles are required before rendering.", "subtitles")
    if subtitles.source == "storyboard" and subtitles.storyboard_version != storyboard.version:
        _raise_missing_input(
            "subtitles_stale_or_missing",
            "Subtitles must match the approved storyboard version before rendering.",
            "subtitles",
        )
    return subtitles


def _required_voice(storage: ProjectStorage, project: Project) -> VoiceConfig:
    voice_config = read_voice_config(storage, project.id)
    if (
        voice_config is None
        or not voice_config.audio_path
        or project.stale_artifacts.get("voice")
        or not storage.project_file_exists(project.id, voice_config.audio_path)
    ):
        _raise_missing_input("voice_audio_not_found", "Narration audio is required before rendering.", "voice_generation")
    return voice_config


def _refresh_project_after_render(storage: ProjectStorage, project: Project, *, mode: RenderMode) -> None:
    next_project = project.model_copy(deep=True)
    next_project.status = ProjectStatus.RENDERED
    next_project.current_step = "final_video_ready" if mode == "final" else "rendered"
    next_project.updated_at = utc_now()
    stale_artifacts = dict(next_project.stale_artifacts)
    stale_artifacts.pop("render", None)
    if mode == "final":
        stale_artifacts.pop("export", None)
    next_project.stale_artifacts = stale_artifacts
    storage.write_json(project.id, PROJECT_METADATA_FILE, next_project)


def _raise_missing_input(code: str, message: str, step: str) -> None:
    raise AppError(
        code=code,
        message=message,
        status_code=409,
        step=step,
        retryable=True,
        suggested_correction="Complete and approve all upstream artifacts before rendering.",
    )
