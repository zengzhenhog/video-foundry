from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from video_foundry.api.dependencies import get_project_storage
from video_foundry.renderer.service import (
    FINAL_OUTPUT_TEMPLATE,
    PREVIEW_OUTPUT_TEMPLATE,
    export_project_video,
    render_project_preview,
)
from video_foundry.shared.config import get_settings
from video_foundry.shared.errors import AppError
from video_foundry.shared.schemas import RenderManifest
from video_foundry.shared.storage import ProjectStorage


router = APIRouter(prefix="/api/projects/{project_id}", tags=["render"])


@router.post("/render", response_model=RenderManifest)
def post_render_project(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> RenderManifest:
    return render_project_preview(storage, project_id, config_dir=get_settings().resolved_config_dir)


@router.post("/export", response_model=RenderManifest)
def post_export_project(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> RenderManifest:
    return export_project_video(storage, project_id, config_dir=get_settings().resolved_config_dir)


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

