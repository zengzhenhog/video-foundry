from __future__ import annotations

from uuid import uuid4

from video_foundry.jobs.models import JobError, JobRecord, JobStatus, PipelineLogEntry
from video_foundry.jobs.store import JobStore
from video_foundry.shared.paths import PROJECT_METADATA_FILE
from video_foundry.shared.schemas import ProjectStatus, utc_now
from video_foundry.shared.storage import ProjectStorage


class JobManager:
    def __init__(self, storage: ProjectStorage) -> None:
        self.storage = storage
        self.store = JobStore(storage)

    def create_job(self, project_id: str, job_type: str, *, summary: str) -> JobRecord:
        project = self.storage.read_project(project_id)
        now = utc_now()
        job = JobRecord(
            id=f"job_{uuid4().hex[:20]}",
            project_id=project.id,
            type=job_type,
            status=JobStatus.PENDING,
            progress=0.0,
            summary=summary,
            created_at=now,
            updated_at=now,
        )
        self.store.write_job(job)
        self._log(job, step=job_type, status=JobStatus.PENDING, summary=summary)
        return job

    def get_job(self, job_id: str) -> JobRecord:
        return self.store.find_job(job_id)

    def start(self, project_id: str, job_id: str, *, step: str, summary: str) -> JobRecord:
        job = self.store.read_job(project_id, job_id)
        now = utc_now()
        next_job = job.model_copy(
            update={
                "status": JobStatus.RUNNING,
                "progress": max(job.progress, 0.01),
                "summary": summary,
                "started_at": job.started_at or now,
                "updated_at": now,
                "finished_at": None,
                "error": None,
            },
            deep=True,
        )
        self.store.clear_error(project_id)
        self.store.write_job(next_job)
        self._log(next_job, step=step, status=JobStatus.RUNNING, summary=summary)
        return next_job

    def update_progress(self, project_id: str, job_id: str, *, progress: float, summary: str) -> JobRecord:
        job = self.store.read_job(project_id, job_id)
        next_job = job.model_copy(
            update={
                "progress": min(0.99, max(0.0, progress)),
                "summary": summary,
                "updated_at": utc_now(),
            },
            deep=True,
        )
        self.store.write_job(next_job)
        self._log(next_job, step=next_job.type, status=next_job.status, summary=summary)
        return next_job

    def succeed(
        self,
        project_id: str,
        job_id: str,
        *,
        output_paths: list[str],
        summary: str,
    ) -> JobRecord:
        job = self.store.read_job(project_id, job_id)
        now = utc_now()
        next_job = job.model_copy(
            update={
                "status": JobStatus.SUCCEEDED,
                "progress": 1.0,
                "summary": summary,
                "updated_at": now,
                "finished_at": now,
                "error": None,
                "output_paths": output_paths,
            },
            deep=True,
        )
        self.store.write_job(next_job)
        self._log(next_job, step=next_job.type, status=JobStatus.SUCCEEDED, summary=summary)
        return next_job

    def fail(self, project_id: str, job_id: str, *, error: JobError) -> JobRecord:
        job = self.store.read_job(project_id, job_id)
        now = utc_now()
        next_job = job.model_copy(
            update={
                "status": JobStatus.FAILED,
                "summary": error.reason,
                "updated_at": now,
                "finished_at": now,
                "error": error,
            },
            deep=True,
        )
        self.store.write_job(next_job)
        self.store.write_error(project_id, error)
        self._mark_project_failed(project_id, error)
        self._log(
            next_job,
            step=error.step,
            status=JobStatus.FAILED,
            summary=error.reason,
            details={"code": error.code, "retryable": error.retryable},
        )
        return next_job

    def _mark_project_failed(self, project_id: str, error: JobError) -> None:
        project = self.storage.read_project(project_id)
        next_project = project.model_copy(
            update={
                "status": ProjectStatus.FAILED,
                "current_step": error.step,
                "updated_at": utc_now(),
            },
            deep=True,
        )
        self.storage.write_json(project.id, PROJECT_METADATA_FILE, next_project)

    def _log(
        self,
        job: JobRecord,
        *,
        step: str,
        status: JobStatus,
        summary: str,
        details: dict | None = None,
    ) -> None:
        self.store.append_log(
            PipelineLogEntry(
                project_id=job.project_id,
                job_id=job.id,
                step=step,
                status=status,
                summary=summary,
                details=details or {},
            )
        )

