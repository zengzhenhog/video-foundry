from __future__ import annotations

from fastapi import APIRouter, Depends

from video_foundry.api.dependencies import get_project_storage
from video_foundry.quality.report import read_quality_report
from video_foundry.shared.schemas import QualityReport
from video_foundry.shared.storage import ProjectStorage


router = APIRouter(prefix="/api/projects/{project_id}", tags=["quality"])


@router.get("/quality-report", response_model=QualityReport)
def get_quality_report(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> QualityReport:
    return read_quality_report(storage, project_id)
