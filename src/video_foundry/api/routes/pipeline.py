from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status

from video_foundry.ai.script_generator import (
    SCRIPT_JSON_PATH,
    SCRIPT_MARKDOWN_PATH,
    generate_project_script,
    read_project_script,
)
from video_foundry.api.dependencies import get_project_storage
from video_foundry.jobs.manager import JobManager
from video_foundry.jobs.models import JobError, JobSubmitResponse
from video_foundry.jobs.runner import JobRunResult, ProgressCallback, enqueue_job
from video_foundry.quality.report import QUALITY_REPORT_PATH, mark_project_exported, require_quality_gate
from video_foundry.renderer.manifest import RENDER_MANIFEST_PATH
from video_foundry.renderer.service import export_project_video, render_project_preview
from video_foundry.shared.config import get_settings
from video_foundry.shared.errors import AppError
from video_foundry.shared.schemas import Project, Script, Storyboard, SubtitlesManifest, VoiceConfig
from video_foundry.shared.storage import ProjectStorage
from video_foundry.sources.upload_importer import read_asset_metadata, summarize_asset_status
from video_foundry.storyboard.planner import (
    STORYBOARD_JSON_PATH,
    generate_project_storyboard,
    read_project_storyboard_optional,
)
from video_foundry.subtitles.generator import (
    SUBTITLES_MANIFEST_PATH,
    SUBTITLES_SRT_PATH,
    SUBTITLES_VTT_PATH,
    generate_project_subtitles,
    read_subtitles_manifest,
)
from video_foundry.voice.provider_registry import (
    NARRATION_RELATIVE_PATH,
    generate_narration,
    read_voice_config,
)


router = APIRouter(prefix="/api/projects/{project_id}", tags=["pipeline"])


@router.post("/generate-all", response_model=JobSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def post_generate_all(
    project_id: str,
    background_tasks: BackgroundTasks,
    storage: ProjectStorage = Depends(get_project_storage),
) -> JobSubmitResponse:
    config_dir = get_settings().resolved_config_dir
    manager = JobManager(storage)
    job = manager.create_job(project_id, "generate_all", summary="Full pipeline queued.")

    def task(progress: ProgressCallback) -> JobRunResult:
        return run_generate_all(storage, project_id, config_dir=config_dir, progress=progress)

    enqueue_job(background_tasks, manager=manager, job=job, step="generate_all", task=task)
    return JobSubmitResponse(job_id=job.id, job=job)


def run_generate_all(
    storage: ProjectStorage,
    project_id: str,
    *,
    config_dir,
    progress: ProgressCallback,
) -> JobRunResult:
    output_paths: list[str] = []
    progress(0.05, "Checking project assets and credit.")
    _require_assets_ready(storage, project_id)

    script = _current_script(storage, project_id)
    project = storage.read_project(project_id)
    if script is None or project.stale_artifacts.get("script"):
        progress(0.14, "Generating script for review.")
        script = generate_project_script(storage, project_id)
        output_paths.extend([SCRIPT_JSON_PATH, SCRIPT_MARKDOWN_PATH])
        return _blocked(
            code="needs_script_approval",
            step="script_review",
            reason="Script has been generated and needs human approval before continuing.",
            suggested_correction="Open the script step, review the generated script, and approve it.",
            output_paths=output_paths,
        )
    if not script.approved:
        return _blocked(
            code="needs_script_approval",
            step="script_review",
            reason="Script needs human approval before continuing.",
            suggested_correction="Open the script step, review the script, and approve it.",
            output_paths=output_paths,
        )

    voice_config = read_voice_config(storage, project_id)
    if voice_config is None:
        return _blocked(
            code="needs_voice_config",
            step="voice_config",
            reason="Voice settings must be saved before narration can be generated.",
            suggested_correction="Open the voice step, save a mock voice configuration, and retry.",
            output_paths=output_paths,
        )
    if _voice_missing_or_stale(storage, project_id, voice_config):
        progress(0.28, "Generating narration audio.")
        voice_config = generate_narration(storage, project_id)
        if voice_config.audio_path:
            output_paths.append(voice_config.audio_path)
        else:
            output_paths.append(NARRATION_RELATIVE_PATH)

    storyboard = _current_storyboard(storage, project_id)
    project = storage.read_project(project_id)
    if storyboard is None or project.stale_artifacts.get("storyboard"):
        progress(0.42, "Generating storyboard for review.")
        storyboard = generate_project_storyboard(storage, project_id, config_dir=config_dir)
        output_paths.append(STORYBOARD_JSON_PATH)
        return _blocked(
            code="needs_storyboard_approval",
            step="storyboard_review",
            reason="Storyboard has been generated and needs human approval before continuing.",
            suggested_correction="Open the storyboard step, review the shots, and approve them.",
            output_paths=output_paths,
        )
    if not storyboard.approved:
        return _blocked(
            code="needs_storyboard_approval",
            step="storyboard_review",
            reason="Storyboard needs human approval before continuing.",
            suggested_correction="Open the storyboard step, review the shots, and approve them.",
            output_paths=output_paths,
        )

    if _subtitles_missing_or_stale(storage, project_id, storyboard):
        progress(0.56, "Generating subtitles from the approved storyboard.")
        generate_project_subtitles(storage, project_id)
        output_paths.extend([SUBTITLES_MANIFEST_PATH, SUBTITLES_SRT_PATH, SUBTITLES_VTT_PATH])

    progress(0.70, "Rendering preview video.")
    preview_manifest = render_project_preview(storage, project_id, config_dir=config_dir)
    output_paths.append(RENDER_MANIFEST_PATH)
    if preview_manifest.preview_output_path:
        output_paths.append(preview_manifest.preview_output_path)

    progress(0.84, "Rendering final video.")
    final_manifest = export_project_video(storage, project_id, config_dir=config_dir)
    output_paths.append(RENDER_MANIFEST_PATH)
    if final_manifest.final_output_path:
        output_paths.append(final_manifest.final_output_path)

    progress(0.94, "Running export quality gate.")
    require_quality_gate(storage, project_id, config_dir=config_dir)
    mark_project_exported(storage, project_id)
    output_paths.append(QUALITY_REPORT_PATH)

    return JobRunResult(
        output_paths=_dedupe(output_paths),
        summary="Pipeline completed. Final MP4 and quality report are ready.",
    )


def _require_assets_ready(storage: ProjectStorage, project_id: str) -> None:
    project = storage.read_project(project_id)
    asset = read_asset_metadata(storage, project.id)
    status = summarize_asset_status(storage, project.id, asset=asset)
    if asset is not None and status.ready_for_script:
        return

    missing: list[str] = []
    if not status.has_original_image:
        missing.append("image")
    if not status.has_preview_image:
        missing.append("preview")
    if not status.has_description:
        missing.append("description")
    if not status.has_source_url:
        missing.append("source_url")
    if not status.has_credit:
        missing.append("credit")
    raise AppError(
        code="asset_not_ready_for_script",
        message="Project assets are not ready for generation.",
        status_code=409,
        step="asset_validation",
        retryable=True,
        suggested_correction="Upload an image and save description, source URL, and credit first.",
        details={"missing": missing},
    )


def _current_script(storage: ProjectStorage, project_id: str) -> Script | None:
    try:
        return read_project_script(storage, project_id)
    except AppError as exc:
        if exc.detail.code == "script_not_found":
            return None
        raise


def _current_storyboard(storage: ProjectStorage, project_id: str) -> Storyboard | None:
    return read_project_storyboard_optional(storage, project_id)


def _voice_missing_or_stale(storage: ProjectStorage, project_id: str, voice_config: VoiceConfig) -> bool:
    project = storage.read_project(project_id)
    return (
        not voice_config.audio_path
        or project.stale_artifacts.get("voice", False)
        or not storage.project_file_exists(project_id, voice_config.audio_path)
    )


def _subtitles_missing_or_stale(
    storage: ProjectStorage,
    project_id: str,
    storyboard: Storyboard,
) -> bool:
    project = storage.read_project(project_id)
    try:
        subtitles = read_subtitles_manifest(storage, project_id)
    except AppError as exc:
        if exc.detail.code == "subtitles_not_found":
            return True
        raise
    return (
        subtitles.stale
        or project.stale_artifacts.get("subtitles", False)
        or not storage.project_file_exists(project_id, subtitles.srt_path)
        or not storage.project_file_exists(project_id, subtitles.vtt_path)
        or subtitles.source != "storyboard"
        or subtitles.storyboard_version != storyboard.version
    )


def _blocked(
    *,
    code: str,
    step: str,
    reason: str,
    suggested_correction: str,
    output_paths: list[str],
) -> JobRunResult:
    return JobRunResult(
        output_paths=_dedupe(output_paths),
        summary=reason,
        blocked_error=JobError(
            code=code,
            step=step,
            reason=reason,
            retryable=True,
            suggested_correction=suggested_correction,
        ),
    )


def _dedupe(paths: list[str]) -> list[str]:
    deduped: list[str] = []
    for path in paths:
        if path and path not in deduped:
            deduped.append(path)
    return deduped
