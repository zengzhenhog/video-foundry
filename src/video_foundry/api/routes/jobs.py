from __future__ import annotations

from fastapi import APIRouter, Depends

from video_foundry.api.dependencies import get_project_storage
from video_foundry.jobs.manager import JobManager
from video_foundry.jobs.models import JobRecord
from video_foundry.shared.storage import ProjectStorage


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRecord)
def get_job(
    job_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> JobRecord:
    return JobManager(storage).get_job(job_id)

