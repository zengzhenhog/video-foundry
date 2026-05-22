from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field

from video_foundry.api.dependencies import get_project_storage
from video_foundry.audio.background_music import read_background_music_metadata
from video_foundry.shared.cache import FileCache
from video_foundry.shared.config import get_settings
from video_foundry.shared.paths import PROJECT_METADATA_FILE
from video_foundry.shared.schemas import DEFAULT_FORMATS, ProjectDetail, utc_now
from video_foundry.shared.storage import ProjectStorage
from video_foundry.sources.nasa_api import NasaApiClient, NasaSearchResponse, NasaSearchResult
from video_foundry.sources.upload_importer import build_project_detail, save_asset_text, save_image_asset
from video_foundry.voice.provider_registry import read_voice_config


router = APIRouter(prefix="/api/imports", tags=["imports"])


class NasaImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: NasaSearchResult
    name: str | None = Field(default=None, max_length=120)
    target_language: str = Field(default="zh-CN", min_length=2, max_length=32)
    target_duration_sec: float = Field(default=60, gt=0, le=3600)
    formats: list[str] = Field(default_factory=lambda: list(DEFAULT_FORMATS), min_length=1)


@router.get("/nasa/search", response_model=NasaSearchResponse)
def search_nasa(
    q: str = Query(min_length=1, max_length=200),
    page_size: int = Query(default=10, ge=1, le=50),
) -> NasaSearchResponse:
    return NasaSearchResponse(results=build_nasa_client().search(q, page_size=page_size))


@router.post(
    "/nasa/projects",
    response_model=ProjectDetail,
    status_code=status.HTTP_201_CREATED,
)
def import_nasa_project(
    request: NasaImportRequest,
    storage: ProjectStorage = Depends(get_project_storage),
) -> ProjectDetail:
    client = build_nasa_client()
    image_url = client.resolve_image_url(request.result)
    image_bytes = client.download_image(image_url)
    project = storage.create_project(
        name=(request.name or request.result.title).strip(),
        target_language=request.target_language,
        target_duration_sec=request.target_duration_sec,
        formats=request.formats,
    )
    save_image_asset(
        storage,
        project,
        original_filename=_filename_for_image_url(image_url),
        content=image_bytes,
        config_dir=get_settings().resolved_config_dir,
    )
    project_after_image = storage.read_project(project.id)
    save_asset_text(
        storage,
        project_after_image,
        title=request.result.title,
        description=request.result.description,
        source_url=request.result.source_url,
        credit=request.result.credit,
    )
    project_after_text = storage.read_project(project.id)
    updated_project = project_after_text.model_copy(
        update={
            "metadata": {
                **project_after_text.metadata,
                "source_import": {
                    "provider": "nasa",
                    "nasa_id": request.result.nasa_id,
                    "asset_manifest_url": request.result.asset_manifest_url,
                    "download_url": image_url,
                    "imported_at": utc_now().isoformat(),
                },
            },
            "updated_at": utc_now(),
        },
        deep=True,
    )
    storage.write_json(project.id, PROJECT_METADATA_FILE, updated_project)
    return build_project_detail(
        storage,
        updated_project,
        background_music=read_background_music_metadata(storage, project.id),
        voice_config=read_voice_config(storage, project.id),
    )


def build_nasa_client() -> NasaApiClient:
    settings = get_settings()
    cache = FileCache(settings.resolved_projects_dir / "_cache", namespace="nasa")
    return NasaApiClient(cache=cache)


def _filename_for_image_url(image_url: str) -> str:
    name = image_url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    return name or "nasa-image"
