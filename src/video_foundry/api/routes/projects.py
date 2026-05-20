from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from video_foundry.api.dependencies import get_project_storage
from video_foundry.audio.background_music import read_background_music_metadata
from video_foundry.shared.schemas import DEFAULT_FORMATS, Project, ProjectDetail
from video_foundry.shared.storage import ProjectStorage
from video_foundry.sources.upload_importer import build_project_detail
from video_foundry.voice.provider_registry import read_voice_config


router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    target_language: str = Field(default="zh-CN", min_length=2, max_length=32)
    target_duration_sec: float = Field(default=60, gt=0, le=3600)
    formats: list[str] = Field(default_factory=lambda: list(DEFAULT_FORMATS), min_length=1)


class ProjectListResponse(BaseModel):
    projects: list[Project]


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(
    request: ProjectCreateRequest,
    storage: ProjectStorage = Depends(get_project_storage),
) -> Project:
    return storage.create_project(
        name=request.name,
        target_language=request.target_language,
        target_duration_sec=request.target_duration_sec,
        formats=request.formats,
    )


@router.get("", response_model=ProjectListResponse)
def list_projects(storage: ProjectStorage = Depends(get_project_storage)) -> ProjectListResponse:
    return ProjectListResponse(projects=storage.list_projects())


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> ProjectDetail:
    project = storage.read_project(project_id)
    return build_project_detail(
        storage,
        project,
        background_music=read_background_music_metadata(storage, project.id),
        voice_config=read_voice_config(storage, project.id),
    )

