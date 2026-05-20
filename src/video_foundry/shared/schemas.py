from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from video_foundry.shared.paths import (
    validate_identifier_value,
    validate_project_id,
    validate_relative_project_path_value,
)


SCHEMA_VERSION = "1.0"
DEFAULT_FORMATS = ["vertical_1080x1920"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    ASSET_READY = "asset_ready"
    SCRIPT_READY = "script_ready"
    SCRIPT_APPROVED = "script_approved"
    STORYBOARD_READY = "storyboard_ready"
    STORYBOARD_APPROVED = "storyboard_approved"
    VOICE_READY = "voice_ready"
    RENDERED = "rendered"
    EXPORTED = "exported"
    FAILED = "failed"


class RenderJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class BaseDiskModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = SCHEMA_VERSION


class Project(BaseDiskModel):
    id: str
    name: str = Field(min_length=1, max_length=120)
    status: ProjectStatus = ProjectStatus.DRAFT
    target_language: str = Field(default="zh-CN", min_length=2, max_length=32)
    target_duration_sec: float = Field(default=60, gt=0, le=3600)
    formats: list[str] = Field(default_factory=lambda: list(DEFAULT_FORMATS), min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    current_step: str = Field(default="project_created", min_length=1, max_length=80)
    stale_artifacts: dict[str, bool] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_project_id(value)

    @field_validator("formats")
    @classmethod
    def validate_formats(cls, value: list[str]) -> list[str]:
        return [validate_identifier_value(item, "format") for item in value]


class Asset(BaseDiskModel):
    project_id: str
    title: str = Field(default="", max_length=240)
    source_url: str | None = Field(default=None, max_length=2048)
    original_filename: str | None = Field(default=None, max_length=240)
    image_original_path: str | None = None
    image_preview_path: str | None = None
    image_format: str | None = Field(default=None, max_length=32)
    description: str = ""
    credit: str = ""
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_project_id(value)

    @field_validator("image_original_path", "image_preview_path")
    @classmethod
    def validate_relative_paths(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_relative_project_path_value(value)


class ScriptSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_sec: float = Field(ge=0)
    end_sec: float = Field(ge=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_time_order(self) -> ScriptSegment:
        if self.end_sec < self.start_sec:
            raise ValueError("Segment end_sec must be greater than or equal to start_sec.")
        return self


class Script(BaseDiskModel):
    project_id: str
    language: str = Field(default="zh-CN", min_length=2, max_length=32)
    duration_target_sec: float = Field(gt=0, le=3600)
    title: str = Field(default="", max_length=240)
    narration: str = Field(default="", max_length=20000)
    segments: list[ScriptSegment] = Field(default_factory=list)
    review_notes: str = Field(default="", max_length=12000)
    approved: bool = False
    updated_at: datetime = Field(default_factory=utc_now)
    approved_at: datetime | None = None

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_project_id(value)


class VoiceConfig(BaseDiskModel):
    provider: str = Field(default="mock", min_length=1, max_length=80)
    voice_id: str = Field(default="default", min_length=1, max_length=120)
    language: str = Field(default="zh-CN", min_length=2, max_length=32)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    volume_gain_db: float = Field(default=0.0, ge=-24.0, le=12.0)
    style: str | None = Field(default=None, max_length=80)
    settings: dict[str, Any] = Field(default_factory=dict)
    audio_path: str | None = None
    duration_sec: float | None = Field(default=None, ge=0)

    @field_validator("audio_path")
    @classmethod
    def validate_audio_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_relative_project_path_value(value)


class BackgroundMusic(BaseDiskModel):
    project_id: str | None = None
    file_path: str
    original_filename: str = Field(min_length=1, max_length=240)
    duration_sec: float | None = Field(default=None, ge=0)
    volume_gain_db: float = Field(default=-18.0, ge=-60.0, le=12.0)
    loop: bool = True
    fade_in_sec: float = Field(default=0.0, ge=0, le=60)
    fade_out_sec: float = Field(default=0.0, ge=0, le=60)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_project_id(value)

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: str) -> str:
        return validate_relative_project_path_value(value)


class AssetStatusSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_original_image: bool = False
    has_preview_image: bool = False
    has_source_url: bool = False
    has_credit: bool = False
    has_description: bool = False
    has_background_music: bool = False
    ready_for_script: bool = False


class ProjectDetail(Project):
    asset: Asset | None = None
    background_music: BackgroundMusic | None = None
    asset_status: AssetStatusSummary = Field(default_factory=AssetStatusSummary)


class StoryboardShot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    start_sec: float = Field(ge=0)
    end_sec: float = Field(ge=0)
    type: str = Field(min_length=1, max_length=80)
    crop_start: tuple[float, float, float, float]
    crop_end: tuple[float, float, float, float]
    easing: str = Field(default="linear", min_length=1, max_length=80)
    caption: str = ""

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_identifier_value(value, "shot_id")

    @field_validator("crop_start", "crop_end")
    @classmethod
    def validate_crop(cls, value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        if len(value) != 4:
            raise ValueError("Crop rectangles must contain exactly four coordinates.")
        x1, y1, x2, y2 = value
        if any(coordinate < 0 or coordinate > 1 for coordinate in value):
            raise ValueError("Crop coordinates must be within [0, 1].")
        if x2 < x1 or y2 < y1:
            raise ValueError("Crop max coordinates must be greater than or equal to min coordinates.")
        return value

    @model_validator(mode="after")
    def validate_time_order(self) -> StoryboardShot:
        if self.end_sec < self.start_sec:
            raise ValueError("Shot end_sec must be greater than or equal to start_sec.")
        return self


class Storyboard(BaseDiskModel):
    project_id: str
    version: int = Field(default=1, ge=1)
    format: str = Field(default="vertical_1080x1920")
    fps: int = Field(default=30, gt=0, le=240)
    duration_sec: float = Field(gt=0, le=3600)
    safe_area: dict[str, float] = Field(
        default_factory=lambda: {"top": 0.08, "bottom": 0.12, "left": 0.06, "right": 0.06}
    )
    shots: list[StoryboardShot] = Field(default_factory=list)
    approved: bool = False
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_project_id(value)

    @field_validator("format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        return validate_identifier_value(value, "format")

    @field_validator("safe_area")
    @classmethod
    def validate_safe_area(cls, value: dict[str, float]) -> dict[str, float]:
        for key, coordinate in value.items():
            if coordinate < 0 or coordinate > 1:
                raise ValueError(f"Safe-area value {key} must be within [0, 1].")
        return value


class RenderJob(BaseDiskModel):
    id: str
    project_id: str
    type: str = Field(min_length=1, max_length=80)
    status: RenderJobStatus = RenderJobStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: dict[str, Any] | None = None
    output_paths: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_identifier_value(value, "job_id")

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_project_id(value)

    @field_validator("output_paths")
    @classmethod
    def validate_output_paths(cls, value: list[str]) -> list[str]:
        return [validate_relative_project_path_value(item, "output_path") for item in value]


class QualityCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)


class QualityReport(BaseDiskModel):
    project_id: str
    passed: bool
    checks: list[QualityCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_project_id(value)

