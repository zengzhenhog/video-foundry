from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from video_foundry.api.dependencies import get_project_storage
from video_foundry.shared.config import get_settings
from video_foundry.shared.schemas import Storyboard, StoryboardShot
from video_foundry.shared.storage import ProjectStorage
from video_foundry.storyboard.planner import (
    approve_project_storyboard,
    generate_project_storyboard,
    read_project_storyboard,
    save_project_storyboard,
)


router = APIRouter(prefix="/api/projects/{project_id}/storyboard", tags=["storyboard"])


class StoryboardGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: str | None = Field(default=None, min_length=1, max_length=80)


class StoryboardUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: str = Field(min_length=1, max_length=80)
    fps: int = Field(gt=0, le=240)
    duration_sec: float = Field(gt=0, le=3600)
    safe_area: dict[str, float] = Field(default_factory=dict)
    shots: list[StoryboardShot] = Field(min_length=1)


@router.post("/generate", response_model=Storyboard)
def generate_storyboard(
    project_id: str,
    request: StoryboardGenerateRequest | None = None,
    storage: ProjectStorage = Depends(get_project_storage),
) -> Storyboard:
    return generate_project_storyboard(
        storage,
        project_id,
        config_dir=get_settings().resolved_config_dir,
        format_name=request.format if request else None,
    )


@router.get("", response_model=Storyboard)
def get_storyboard(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> Storyboard:
    return read_project_storyboard(storage, project_id)


@router.put("", response_model=Storyboard)
def update_storyboard(
    project_id: str,
    request: StoryboardUpdateRequest,
    storage: ProjectStorage = Depends(get_project_storage),
) -> Storyboard:
    return save_project_storyboard(
        storage,
        project_id,
        Storyboard(
            project_id=project_id,
            format=request.format,
            fps=request.fps,
            duration_sec=request.duration_sec,
            safe_area=request.safe_area,
            shots=request.shots,
            approved=False,
        ),
        config_dir=get_settings().resolved_config_dir,
    )


@router.post("/approve", response_model=Storyboard)
def approve_storyboard(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> Storyboard:
    return approve_project_storyboard(storage, project_id, config_dir=get_settings().resolved_config_dir)

