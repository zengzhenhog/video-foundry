from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from video_foundry.api.dependencies import get_project_storage
from video_foundry.jobs.models import ProjectLogsResponse
from video_foundry.jobs.store import JobStore
from video_foundry.shared.storage import ProjectStorage


router = APIRouter(prefix="/api/projects/{project_id}", tags=["logs"])


@router.get("/logs", response_model=ProjectLogsResponse)
def get_project_logs(
    project_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    storage: ProjectStorage = Depends(get_project_storage),
) -> ProjectLogsResponse:
    return JobStore(storage).read_logs(project_id, limit=limit)

