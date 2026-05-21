from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import FileResponse

from video_foundry.api.dependencies import get_project_storage
from video_foundry.jobs.manager import JobManager
from video_foundry.jobs.models import JobSubmitResponse
from video_foundry.jobs.runner import JobRunResult, ProgressCallback, enqueue_job
from video_foundry.quality.report import QUALITY_REPORT_PATH, mark_project_exported, require_quality_gate
from video_foundry.renderer.manifest import RENDER_MANIFEST_PATH
from video_foundry.renderer.service import (
    FINAL_OUTPUT_TEMPLATE,
    PREVIEW_OUTPUT_TEMPLATE,
    export_project_video,
    render_project_preview,
)
from video_foundry.shared.config import get_settings
from video_foundry.shared.errors import AppError
from video_foundry.shared.storage import ProjectStorage


router = APIRouter(prefix="/api/projects/{project_id}", tags=["render"])


@router.post("/render", response_model=JobSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def post_render_project(
    project_id: str,
    background_tasks: BackgroundTasks,
    storage: ProjectStorage = Depends(get_project_storage),
) -> JobSubmitResponse:
    config_dir = get_settings().resolved_config_dir
    manager = JobManager(storage)
    job = manager.create_job(project_id, "render_preview", summary="Preview render queued.")

    def task(progress: ProgressCallback) -> JobRunResult:
        progress(0.08, "Rendering preview frames and assembling preview video.")
        manifest = render_project_preview(storage, project_id, config_dir=config_dir)
        output_paths = [RENDER_MANIFEST_PATH]
        if manifest.preview_output_path:
            output_paths.append(manifest.preview_output_path)
        return JobRunResult(output_paths=output_paths, summary="Preview render completed.")

    enqueue_job(background_tasks, manager=manager, job=job, step="render_preview", task=task)
    return JobSubmitResponse(job_id=job.id, job=job)


@router.post("/export", response_model=JobSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def post_export_project(
    project_id: str,
    background_tasks: BackgroundTasks,
    storage: ProjectStorage = Depends(get_project_storage),
) -> JobSubmitResponse:
    config_dir = get_settings().resolved_config_dir
    manager = JobManager(storage)
    job = manager.create_job(project_id, "export_final", summary="Final export queued.")

    def task(progress: ProgressCallback) -> JobRunResult:
        progress(0.08, "Rendering final frames and assembling final video.")
        manifest = export_project_video(storage, project_id, config_dir=config_dir)
        progress(0.82, "Running export quality gate.")
        require_quality_gate(storage, project_id, config_dir=config_dir)
        mark_project_exported(storage, project_id)
        output_paths = [RENDER_MANIFEST_PATH, QUALITY_REPORT_PATH]
        if manifest.final_output_path:
            output_paths.append(manifest.final_output_path)
        return JobRunResult(output_paths=output_paths, summary="Final export passed quality checks.")

    enqueue_job(background_tasks, manager=manager, job=job, step="export_final", task=task)
    return JobSubmitResponse(job_id=job.id, job=job)


@router.get("/render/preview")
def get_render_preview(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> FileResponse:
    project = storage.read_project(project_id)
    format_name = project.formats[0]
    return _video_response(storage, project.id, PREVIEW_OUTPUT_TEMPLATE.format(format=format_name))


@router.get("/export/video")
def get_export_video(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> FileResponse:
    project = storage.read_project(project_id)
    format_name = project.formats[0]
    return _video_response(storage, project.id, FINAL_OUTPUT_TEMPLATE.format(format=format_name))


def _video_response(storage: ProjectStorage, project_id: str, relative_path: str) -> FileResponse:
    path = storage.resolve_project_path(project_id, relative_path)
    if not path.exists():
        raise AppError(
            code="render_output_not_found",
            message="Rendered video output was not found.",
            status_code=404,
            step="render_output",
            retryable=True,
            suggested_correction="Render or export the project first.",
        )
    return FileResponse(path, media_type="video/mp4", filename=path.name)
