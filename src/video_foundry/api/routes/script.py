from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from video_foundry.ai.script_generator import (
    approve_script,
    generate_project_script,
    read_project_script,
    save_project_script,
)
from video_foundry.api.dependencies import get_project_storage
from video_foundry.shared.schemas import Script, ScriptSegment
from video_foundry.shared.storage import ProjectStorage


router = APIRouter(prefix="/api/projects/{project_id}/script", tags=["script"])


class ScriptGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_draft: str | None = Field(default=None, max_length=20000)


class ScriptUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = Field(default="zh-CN", min_length=2, max_length=32)
    duration_target_sec: float = Field(gt=0, le=3600)
    title: str = Field(default="", max_length=240)
    narration: str = Field(min_length=1, max_length=20000)
    segments: list[ScriptSegment] = Field(min_length=1)
    review_notes: str = Field(min_length=1, max_length=12000)


@router.post("/generate", response_model=Script)
def generate_script(
    project_id: str,
    request: ScriptGenerateRequest | None = None,
    storage: ProjectStorage = Depends(get_project_storage),
) -> Script:
    return generate_project_script(
        storage,
        project_id,
        user_draft=request.user_draft if request else None,
    )


@router.get("", response_model=Script)
def get_script(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> Script:
    return read_project_script(storage, project_id)


@router.put("", response_model=Script)
def update_script(
    project_id: str,
    request: ScriptUpdateRequest,
    storage: ProjectStorage = Depends(get_project_storage),
) -> Script:
    return save_project_script(
        storage,
        project_id,
        Script(
            project_id=project_id,
            language=request.language,
            duration_target_sec=request.duration_target_sec,
            title=request.title,
            narration=request.narration,
            segments=request.segments,
            review_notes=request.review_notes,
            approved=False,
        ),
    )


@router.post("/approve", response_model=Script)
def approve_project_script(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> Script:
    return approve_script(storage, project_id)
