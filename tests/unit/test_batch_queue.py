from __future__ import annotations

from pathlib import Path

from video_foundry.jobs.concurrency import RenderConcurrencyLimiter
from video_foundry.jobs.models import JobError, JobStatus
from video_foundry.jobs.queue import BatchItemStatus, BatchQueueManager
from video_foundry.shared.errors import AppError
from video_foundry.shared.storage import ProjectStorage


def test_batch_queue_claims_pauses_and_marks_failure_without_losing_other_items(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    first = storage.create_project(name="First")
    second = storage.create_project(name="Second")
    manager = BatchQueueManager(storage)

    items = manager.enqueue([first.id, second.id], max_attempts=1)
    manager.pause(items[1].id)
    claimed = manager.claim_next()

    assert claimed is not None
    assert claimed.project_id == first.id
    failed = manager.mark_from_job(
        claimed.id,
        JobStatus.FAILED,
        JobError(code="boom", step="test", reason="Failed.", retryable=True),
        "Failed.",
    )

    assert failed.status is BatchItemStatus.FAILED
    assert [item.status for item in manager.list_items()] == [
        BatchItemStatus.FAILED,
        BatchItemStatus.PAUSED,
    ]


def test_render_concurrency_limiter_rejects_when_no_slot_available() -> None:
    limiter = RenderConcurrencyLimiter(max_concurrent=1)
    with limiter.acquire():
        try:
            with limiter.acquire(blocking=False):
                raise AssertionError("second acquire should fail")
        except AppError as exc:
            assert exc.detail.code == "render_concurrency_limit_reached"

