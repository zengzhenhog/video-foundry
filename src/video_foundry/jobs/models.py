from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from video_foundry.shared.errors import AppError
from video_foundry.shared.paths import (
    validate_identifier_value,
    validate_project_id,
    validate_relative_project_path_value,
)
from video_foundry.shared.schemas import SCHEMA_VERSION, utc_now


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=120)
    step: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=1000)
    retryable: bool = False
    suggested_correction: str | None = Field(default=None, max_length=1000)
    details: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_app_error(cls, error: AppError) -> JobError:
        detail = error.detail
        return cls(
            code=detail.code,
            step=detail.step or "job_execution",
            reason=detail.message,
            retryable=detail.retryable,
            suggested_correction=detail.suggested_correction,
            details=detail.details,
        )

    @classmethod
    def from_exception(cls, error: Exception, *, step: str) -> JobError:
        return cls(
            code="job_failed",
            step=step,
            reason="The job failed unexpectedly.",
            retryable=True,
            suggested_correction="Retry the job. If it fails again, inspect the project logs.",
            details={"exception_type": type(error).__name__},
        )


class JobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    id: str
    project_id: str
    type: str = Field(min_length=1, max_length=80)
    status: JobStatus = JobStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = Field(default="", max_length=1000)
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    error: JobError | None = None
    output_paths: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_identifier_value(value, "job_id")

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_project_id(value)

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        return validate_identifier_value(value, "job_type")

    @field_validator("output_paths")
    @classmethod
    def validate_output_paths(cls, value: list[str]) -> list[str]:
        return [validate_relative_project_path_value(item, "output_path") for item in value]


class JobSubmitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    job: JobRecord


class PipelineLogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(default_factory=utc_now)
    project_id: str
    job_id: str | None = None
    step: str = Field(min_length=1, max_length=120)
    status: JobStatus
    summary: str = Field(min_length=1, max_length=1000)
    details: dict[str, Any] = Field(default_factory=dict)

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


class ProjectLogsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    entries: list[PipelineLogEntry] = Field(default_factory=list)
    error: JobError | None = None

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_project_id(value)

