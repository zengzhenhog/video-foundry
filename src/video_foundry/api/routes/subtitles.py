from __future__ import annotations

from fastapi import APIRouter, Depends

from video_foundry.api.dependencies import get_project_storage
from video_foundry.shared.schemas import SubtitlesManifest
from video_foundry.shared.storage import ProjectStorage
from video_foundry.subtitles.generator import generate_project_subtitles


router = APIRouter(prefix="/api/projects/{project_id}/subtitles", tags=["subtitles"])


@router.post("/generate", response_model=SubtitlesManifest)
def generate_subtitles(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> SubtitlesManifest:
    return generate_project_subtitles(storage, project_id)

