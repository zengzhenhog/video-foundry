from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from video_foundry.api.dependencies import get_project_storage
from video_foundry.audio.background_music import save_background_music
from video_foundry.shared.config import get_settings
from video_foundry.shared.errors import AppError
from video_foundry.shared.schemas import Asset, BackgroundMusic
from video_foundry.shared.storage import ProjectStorage
from video_foundry.sources.upload_importer import (
    read_asset_metadata,
    save_asset_text,
    save_image_asset,
)


router = APIRouter(prefix="/api/projects/{project_id}/assets", tags=["assets"])


class AssetTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=240)
    description: str = ""
    source_url: str | None = Field(default=None, max_length=2048)
    credit: str = Field(default="", max_length=500)


@router.post("/image", response_model=Asset, status_code=status.HTTP_201_CREATED)
async def upload_image_asset(
    project_id: str,
    file: UploadFile = File(...),
    storage: ProjectStorage = Depends(get_project_storage),
) -> Asset:
    project = storage.read_project(project_id)
    content = await file.read()
    return save_image_asset(
        storage,
        project,
        original_filename=file.filename or "upload",
        content=content,
        config_dir=get_settings().resolved_config_dir,
    )


@router.post("/text", response_model=Asset)
def save_text_asset(
    project_id: str,
    request: AssetTextRequest,
    storage: ProjectStorage = Depends(get_project_storage),
) -> Asset:
    project = storage.read_project(project_id)
    return save_asset_text(
        storage,
        project,
        title=request.title,
        description=request.description,
        source_url=request.source_url,
        credit=request.credit,
    )


@router.post(
    "/background-music",
    response_model=BackgroundMusic,
    status_code=status.HTTP_201_CREATED,
)
async def upload_background_music(
    project_id: str,
    file: UploadFile = File(...),
    storage: ProjectStorage = Depends(get_project_storage),
) -> BackgroundMusic:
    project = storage.read_project(project_id)
    content = await file.read()
    return save_background_music(
        storage,
        project,
        original_filename=file.filename or "background_music",
        content=content,
    )


@router.get("/preview")
def get_asset_preview(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> FileResponse:
    storage.read_project(project_id)
    asset = read_asset_metadata(storage, project_id)
    if asset is None or asset.image_preview_path is None:
        raise AppError(
            code="asset_preview_not_found",
            message="Asset preview has not been generated.",
            status_code=404,
            step="asset_preview",
            retryable=True,
            suggested_correction="Upload a valid image first.",
        )

    preview_path = storage.resolve_project_path(project_id, asset.image_preview_path)
    if not preview_path.exists():
        raise AppError(
            code="asset_preview_not_found",
            message="Asset preview file was not found.",
            status_code=404,
            step="asset_preview",
            retryable=True,
            suggested_correction="Upload the image again to regenerate the preview.",
        )
    return FileResponse(preview_path, media_type="image/jpeg", filename="preview.jpg")

