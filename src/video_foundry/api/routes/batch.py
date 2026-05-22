from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from video_foundry.api.dependencies import get_project_storage
from video_foundry.jobs.queue import (
    BatchAction,
    BatchQueueItem,
    BatchQueueManager,
    BatchQueueResponse,
    run_batch_queue,
)
from video_foundry.shared.config import get_settings
from video_foundry.shared.storage import ProjectStorage


router = APIRouter(prefix="/api/batch", tags=["batch"])


class BatchEnqueueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_ids: list[str] = Field(min_length=1)
    action: BatchAction = BatchAction.GENERATE_ALL
    max_attempts: int = Field(default=2, ge=1, le=10)


@router.get("/queue", response_model=BatchQueueResponse)
def list_batch_queue(storage: ProjectStorage = Depends(get_project_storage)) -> BatchQueueResponse:
    return BatchQueueResponse(items=BatchQueueManager(storage).list_items())


@router.post("/queue", response_model=BatchQueueResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_batch(
    request: BatchEnqueueRequest,
    background_tasks: BackgroundTasks,
    storage: ProjectStorage = Depends(get_project_storage),
) -> BatchQueueResponse:
    manager = BatchQueueManager(storage)
    manager.enqueue(request.project_ids, action=request.action, max_attempts=request.max_attempts)
    _schedule_runner(background_tasks, storage)
    return BatchQueueResponse(items=manager.list_items())


@router.post("/queue/run", response_model=BatchQueueResponse, status_code=status.HTTP_202_ACCEPTED)
def run_queue(
    background_tasks: BackgroundTasks,
    storage: ProjectStorage = Depends(get_project_storage),
) -> BatchQueueResponse:
    _schedule_runner(background_tasks, storage)
    return BatchQueueResponse(items=BatchQueueManager(storage).list_items())


@router.post("/queue/{item_id}/pause", response_model=BatchQueueItem)
def pause_batch_item(
    item_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> BatchQueueItem:
    return BatchQueueManager(storage).pause(item_id)


@router.post("/queue/{item_id}/resume", response_model=BatchQueueItem, status_code=status.HTTP_202_ACCEPTED)
def resume_batch_item(
    item_id: str,
    background_tasks: BackgroundTasks,
    storage: ProjectStorage = Depends(get_project_storage),
) -> BatchQueueItem:
    item = BatchQueueManager(storage).resume(item_id)
    _schedule_runner(background_tasks, storage)
    return item


@router.post("/queue/{item_id}/retry", response_model=BatchQueueItem, status_code=status.HTTP_202_ACCEPTED)
def retry_batch_item(
    item_id: str,
    background_tasks: BackgroundTasks,
    storage: ProjectStorage = Depends(get_project_storage),
) -> BatchQueueItem:
    item = BatchQueueManager(storage).retry(item_id)
    _schedule_runner(background_tasks, storage)
    return item


def _schedule_runner(background_tasks: BackgroundTasks, storage: ProjectStorage) -> None:
    background_tasks.add_task(
        run_batch_queue,
        storage,
        config_dir=get_settings().resolved_config_dir,
    )
