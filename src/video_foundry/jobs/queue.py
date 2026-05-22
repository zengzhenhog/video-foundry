from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from video_foundry.jobs.manager import JobManager
from video_foundry.jobs.models import JobError, JobStatus
from video_foundry.jobs.runner import JobRunResult, run_job
from video_foundry.shared.errors import AppError
from video_foundry.shared.paths import validate_identifier_value, validate_project_id
from video_foundry.shared.schemas import SCHEMA_VERSION, utc_now
from video_foundry.shared.storage import ProjectStorage


BATCH_QUEUE_FILE = "_batch_queue.json"


class BatchAction(StrEnum):
    GENERATE_ALL = "generate_all"


class BatchItemStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    id: str
    project_id: str
    action: BatchAction = BatchAction.GENERATE_ALL
    status: BatchItemStatus = BatchItemStatus.PENDING
    attempts: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=2, ge=1, le=10)
    job_id: str | None = None
    summary: str = ""
    error: JobError | None = None
    created_at: object = Field(default_factory=utc_now)
    updated_at: object = Field(default_factory=utc_now)
    finished_at: object | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_identifier_value(value, "batch_item_id")

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_project_id(value)

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_identifier_value(value, "job_id")


class BatchQueueState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    updated_at: object = Field(default_factory=utc_now)
    items: list[BatchQueueItem] = Field(default_factory=list)


class BatchQueueResponse(BaseModel):
    items: list[BatchQueueItem]


class BatchQueueManager:
    def __init__(self, storage: ProjectStorage) -> None:
        self.storage = storage
        self.path = self.storage.projects_root / BATCH_QUEUE_FILE

    def list_items(self) -> list[BatchQueueItem]:
        return self._read_state().items

    def enqueue(
        self,
        project_ids: list[str],
        *,
        action: BatchAction = BatchAction.GENERATE_ALL,
        max_attempts: int = 2,
    ) -> list[BatchQueueItem]:
        state = self._read_state()
        added: list[BatchQueueItem] = []
        active = {
            (item.project_id, item.action): item
            for item in state.items
            if item.status in {BatchItemStatus.PENDING, BatchItemStatus.RUNNING, BatchItemStatus.PAUSED}
        }
        for project_id in project_ids:
            project = self.storage.read_project(project_id)
            existing = active.get((project.id, action))
            if existing is not None:
                added.append(existing)
                continue
            item = BatchQueueItem(
                id=f"batch_{uuid4().hex[:20]}",
                project_id=project.id,
                action=action,
                max_attempts=max_attempts,
                summary="Queued.",
            )
            state.items.append(item)
            added.append(item)
        self._write_state(state)
        return added

    def pause(self, item_id: str) -> BatchQueueItem:
        return self._update_item(
            item_id,
            allowed={BatchItemStatus.PENDING, BatchItemStatus.RUNNING},
            status=BatchItemStatus.PAUSED,
            summary="Paused.",
        )

    def resume(self, item_id: str) -> BatchQueueItem:
        return self._update_item(
            item_id,
            allowed={BatchItemStatus.PAUSED},
            status=BatchItemStatus.PENDING,
            summary="Queued.",
            clear_error=True,
        )

    def retry(self, item_id: str) -> BatchQueueItem:
        state = self._read_state()
        item = self._find_item(state, item_id)
        if item.status not in {BatchItemStatus.FAILED, BatchItemStatus.BLOCKED, BatchItemStatus.CANCELLED}:
            raise _invalid_transition(item)
        next_max_attempts = max(item.max_attempts, item.attempts + 1)
        next_item = item.model_copy(
            update={
                "status": BatchItemStatus.PENDING,
                "summary": "Queued for retry.",
                "error": None,
                "finished_at": None,
                "updated_at": utc_now(),
                "max_attempts": next_max_attempts,
            },
            deep=True,
        )
        self._replace_item(state, next_item)
        self._write_state(state)
        return next_item

    def claim_next(self) -> BatchQueueItem | None:
        state = self._read_state()
        for item in state.items:
            if item.status is not BatchItemStatus.PENDING:
                continue
            next_item = item.model_copy(
                update={
                    "status": BatchItemStatus.RUNNING,
                    "attempts": item.attempts + 1,
                    "summary": "Running.",
                    "updated_at": utc_now(),
                    "finished_at": None,
                    "error": None,
                },
                deep=True,
            )
            self._replace_item(state, next_item)
            self._write_state(state)
            return next_item
        return None

    def attach_job(self, item_id: str, job_id: str) -> BatchQueueItem:
        state = self._read_state()
        item = self._find_item(state, item_id)
        next_item = item.model_copy(update={"job_id": job_id, "updated_at": utc_now()}, deep=True)
        self._replace_item(state, next_item)
        self._write_state(state)
        return next_item

    def mark_from_job(self, item_id: str, job_status: JobStatus, error: JobError | None, summary: str) -> BatchQueueItem:
        state = self._read_state()
        item = self._find_item(state, item_id)
        now = utc_now()
        if job_status is JobStatus.SUCCEEDED:
            next_status = BatchItemStatus.SUCCEEDED
            next_error = None
            finished_at = now
        elif job_status is JobStatus.BLOCKED:
            next_status = BatchItemStatus.BLOCKED
            next_error = error
            finished_at = now
        elif item.attempts < item.max_attempts:
            next_status = BatchItemStatus.PENDING
            next_error = error
            finished_at = None
            summary = f"{summary} Retrying ({item.attempts}/{item.max_attempts})."
        else:
            next_status = BatchItemStatus.FAILED
            next_error = error
            finished_at = now

        next_item = item.model_copy(
            update={
                "status": next_status,
                "summary": summary,
                "error": next_error,
                "updated_at": now,
                "finished_at": finished_at,
            },
            deep=True,
        )
        self._replace_item(state, next_item)
        self._write_state(state)
        return next_item

    def _update_item(
        self,
        item_id: str,
        *,
        allowed: set[BatchItemStatus],
        status: BatchItemStatus,
        summary: str,
        clear_error: bool = False,
    ) -> BatchQueueItem:
        state = self._read_state()
        item = self._find_item(state, item_id)
        if item.status not in allowed:
            raise _invalid_transition(item)
        next_item = item.model_copy(
            update={
                "status": status,
                "summary": summary,
                "error": None if clear_error else item.error,
                "updated_at": utc_now(),
            },
            deep=True,
        )
        self._replace_item(state, next_item)
        self._write_state(state)
        return next_item

    def _read_state(self) -> BatchQueueState:
        if not self.path.exists():
            return BatchQueueState()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return BatchQueueState.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AppError(
                code="batch_queue_invalid",
                message="Batch queue metadata is invalid.",
                status_code=500,
                step="batch_queue",
                retryable=False,
                suggested_correction="Repair or remove the batch queue metadata file.",
            ) from exc

    def _write_state(self, state: BatchQueueState) -> Path:
        self.storage.projects_root.mkdir(parents=True, exist_ok=True)
        next_state = state.model_copy(update={"updated_at": utc_now()}, deep=True)
        self.path.write_text(
            json.dumps(next_state.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return self.path

    def _find_item(self, state: BatchQueueState, item_id: str) -> BatchQueueItem:
        safe_item_id = validate_identifier_value(item_id, "batch_item_id")
        for item in state.items:
            if item.id == safe_item_id:
                return item
        raise AppError(
            code="batch_item_not_found",
            message="Batch queue item was not found.",
            status_code=404,
            step="batch_queue",
            retryable=False,
            suggested_correction="Refresh the batch queue and retry.",
        )

    def _replace_item(self, state: BatchQueueState, next_item: BatchQueueItem) -> None:
        for index, item in enumerate(state.items):
            if item.id == next_item.id:
                state.items[index] = next_item
                return
        state.items.append(next_item)


def run_batch_queue(
    storage: ProjectStorage,
    *,
    config_dir: Path,
    max_items: int | None = None,
) -> None:
    from video_foundry.api.routes.pipeline import run_generate_all

    manager = BatchQueueManager(storage)
    processed = 0
    while max_items is None or processed < max_items:
        item = manager.claim_next()
        if item is None:
            return
        project_manager = JobManager(storage)
        job = project_manager.create_job(item.project_id, item.action.value, summary="Batch item queued.")
        manager.attach_job(item.id, job.id)

        def task(progress):
            return run_generate_all(storage, item.project_id, config_dir=config_dir, progress=progress)

        run_job(project_manager, item.project_id, job.id, item.action.value, task)
        finished_job = project_manager.get_job(job.id)
        manager.mark_from_job(
            item.id,
            finished_job.status,
            finished_job.error,
            finished_job.summary,
        )
        processed += 1


def _invalid_transition(item: BatchQueueItem) -> AppError:
    return AppError(
        code="batch_item_invalid_transition",
        message="Batch item cannot transition from its current status.",
        status_code=409,
        step="batch_queue",
        retryable=False,
        suggested_correction="Refresh the queue and choose a valid action for the item.",
        details={"item_id": item.id, "status": item.status},
    )
