from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from auto_image.api.dependencies import get_project_storage
from auto_image.shared.schemas import DEFAULT_FORMATS, Project
from auto_image.shared.storage import ProjectStorage


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


@router.get("/{project_id}", response_model=Project)
def get_project(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> Project:
    return storage.read_project(project_id)
