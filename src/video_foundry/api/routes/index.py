from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from video_foundry.api.dependencies import get_project_storage
from video_foundry.shared.index_store import (
    ProjectIndexListResponse,
    ProjectIndexRebuildResponse,
    ProjectIndexStore,
)
from video_foundry.shared.storage import ProjectStorage


router = APIRouter(prefix="/api/index", tags=["index"])


@router.post("/rebuild", response_model=ProjectIndexRebuildResponse)
def rebuild_project_index(
    storage: ProjectStorage = Depends(get_project_storage),
) -> ProjectIndexRebuildResponse:
    store = ProjectIndexStore(storage.projects_root)
    return ProjectIndexRebuildResponse(indexed=store.rebuild(storage))


@router.get("/projects", response_model=ProjectIndexListResponse)
def list_indexed_projects(
    query: str | None = Query(default=None, max_length=120),
    status: str | None = Query(default=None, max_length=80),
    storage: ProjectStorage = Depends(get_project_storage),
) -> ProjectIndexListResponse:
    store = ProjectIndexStore(storage.projects_root)
    return ProjectIndexListResponse(projects=store.list_projects(query=query, status=status))
