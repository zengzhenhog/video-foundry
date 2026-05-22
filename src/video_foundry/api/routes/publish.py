from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from video_foundry.api.dependencies import get_project_storage
from video_foundry.shared.storage import ProjectStorage


router = APIRouter(prefix="/api/projects/{project_id}/publish", tags=["publish"])


class PublishPrepareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str = Field(default="placeholder", min_length=1, max_length=80)


class PublishPrepareResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    platform: str
    ready: bool
    message: str


@router.post("/prepare", response_model=PublishPrepareResponse)
def prepare_publish(
    project_id: str,
    request: PublishPrepareRequest,
    storage: ProjectStorage = Depends(get_project_storage),
) -> PublishPrepareResponse:
    project = storage.read_project(project_id)
    return PublishPrepareResponse(
        project_id=project.id,
        platform=request.platform,
        ready=False,
        message="Publishing integration is reserved for a future phase; no external service was contacted.",
    )
