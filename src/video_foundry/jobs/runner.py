from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import BackgroundTasks

from video_foundry.jobs.manager import JobManager
from video_foundry.jobs.models import JobError, JobRecord
from video_foundry.shared.errors import AppError


ProgressCallback = Callable[[float, str], None]
JobTask = Callable[[ProgressCallback], "JobRunResult"]


@dataclass(frozen=True)
class JobRunResult:
    output_paths: list[str] = field(default_factory=list)
    summary: str = "Job completed."
    blocked_error: JobError | None = None


def enqueue_job(
    background_tasks: BackgroundTasks,
    *,
    manager: JobManager,
    job: JobRecord,
    step: str,
    task: JobTask,
) -> None:
    background_tasks.add_task(run_job, manager, job.project_id, job.id, step, task)


def run_job(
    manager: JobManager,
    project_id: str,
    job_id: str,
    step: str,
    task: JobTask,
) -> None:
    manager.start(project_id, job_id, step=step, summary="Job started.")

    def progress(value: float, summary: str) -> None:
        manager.update_progress(project_id, job_id, progress=value, summary=summary)

    try:
        result = task(progress)
    except AppError as exc:
        manager.fail(project_id, job_id, error=JobError.from_app_error(exc))
        return
    except Exception as exc:  # pragma: no cover - defensive guard against leaking tracebacks.
        manager.fail(project_id, job_id, error=JobError.from_exception(exc, step=step))
        return

    if result.blocked_error:
        manager.block(
            project_id,
            job_id,
            error=result.blocked_error,
            output_paths=result.output_paths,
            summary=result.summary,
        )
        return

    manager.succeed(project_id, job_id, output_paths=result.output_paths, summary=result.summary)
