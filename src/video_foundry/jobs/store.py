from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from video_foundry.jobs.models import JobError, JobRecord, PipelineLogEntry, ProjectLogsResponse
from video_foundry.shared.errors import AppError
from video_foundry.shared.paths import validate_identifier_value
from video_foundry.shared.storage import ProjectStorage


JOBS_RELATIVE_DIR = "logs/jobs"
PIPELINE_LOG_PATH = "logs/pipeline.log"
ERROR_JSON_PATH = "logs/error.json"


class JobStore:
    def __init__(self, storage: ProjectStorage) -> None:
        self.storage = storage

    def write_job(self, job: JobRecord) -> Path:
        return self.storage.write_json(job.project_id, job_relative_path(job.id), job)

    def read_job(self, project_id: str, job_id: str) -> JobRecord:
        try:
            data = self.storage.read_json(project_id, job_relative_path(job_id))
        except AppError as exc:
            if exc.detail.code == "project_file_not_found":
                raise AppError(
                    code="job_not_found",
                    message="Job was not found.",
                    status_code=404,
                    step="job_storage",
                    retryable=False,
                    suggested_correction="Check the job id and retry.",
                ) from exc
            raise
        return _validate_job(data)

    def find_job(self, job_id: str) -> JobRecord:
        validate_identifier_value(job_id, "job_id")
        root = self.storage.projects_root
        if root.exists():
            for project_path in sorted(root.iterdir(), key=lambda item: item.name):
                if not project_path.is_dir():
                    continue
                candidate = project_path / JOBS_RELATIVE_DIR / f"{job_id}.json"
                if not candidate.exists():
                    continue
                try:
                    data = json.loads(candidate.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    raise AppError(
                        code="job_metadata_invalid",
                        message="Job metadata JSON is corrupted.",
                        status_code=500,
                        step="job_storage",
                        retryable=False,
                        suggested_correction="Inspect the job JSON file and restore a valid record.",
                    ) from exc
                return _validate_job(data)
        raise AppError(
            code="job_not_found",
            message="Job was not found.",
            status_code=404,
            step="job_storage",
            retryable=False,
            suggested_correction="Check the job id and retry.",
        )

    def append_log(self, entry: PipelineLogEntry) -> None:
        self.storage.read_project(entry.project_id)
        path = self.storage.resolve_project_path(entry.project_id, PIPELINE_LOG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n")

    def read_logs(self, project_id: str, *, limit: int = 100) -> ProjectLogsResponse:
        self.storage.read_project(project_id)
        entries: list[PipelineLogEntry] = []
        path = self.storage.resolve_project_path(project_id, PIPELINE_LOG_PATH)
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            for line in lines[-limit:]:
                try:
                    entries.append(PipelineLogEntry.model_validate(json.loads(line)))
                except (json.JSONDecodeError, ValidationError):
                    continue

        error: JobError | None = None
        error_path = self.storage.resolve_project_path(project_id, ERROR_JSON_PATH)
        if error_path.exists():
            try:
                error = JobError.model_validate(json.loads(error_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, ValidationError):
                error = JobError(
                    code="error_metadata_invalid",
                    step="job_storage",
                    reason="The latest error file could not be parsed.",
                    retryable=False,
                    suggested_correction="Inspect logs/error.json and restore or remove the invalid file.",
                )
        return ProjectLogsResponse(project_id=project_id, entries=entries, error=error)

    def write_error(self, project_id: str, error: JobError) -> None:
        self.storage.write_json(project_id, ERROR_JSON_PATH, error.model_dump(mode="json"))

    def clear_error(self, project_id: str) -> None:
        path = self.storage.resolve_project_path(project_id, ERROR_JSON_PATH)
        if path.exists():
            path.unlink()


def job_relative_path(job_id: str) -> str:
    safe_job_id = validate_identifier_value(job_id, "job_id")
    return f"{JOBS_RELATIVE_DIR}/{safe_job_id}.json"


def _validate_job(data: dict) -> JobRecord:
    try:
        return JobRecord.model_validate(data)
    except ValidationError as exc:
        raise AppError(
            code="job_metadata_invalid",
            message="Job metadata is invalid.",
            status_code=500,
            step="job_storage",
            retryable=False,
            suggested_correction="Inspect the job JSON file and restore a valid record.",
            details={"errors": exc.errors(include_url=False, include_input=False)},
        ) from exc

