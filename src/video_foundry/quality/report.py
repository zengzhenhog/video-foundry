from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from video_foundry.quality.checks import run_quality_checks
from video_foundry.shared.errors import AppError
from video_foundry.shared.paths import PROJECT_METADATA_FILE
from video_foundry.shared.schemas import ProjectStatus, QualityReport, utc_now
from video_foundry.shared.storage import ProjectStorage


QUALITY_REPORT_PATH = "exports/quality-report.json"


def generate_quality_report(
    storage: ProjectStorage,
    project_id: str,
    *,
    config_dir: Path,
) -> QualityReport:
    report = run_quality_checks(storage, project_id, config_dir=config_dir)
    storage.write_json(project_id, QUALITY_REPORT_PATH, report)
    return report


def read_quality_report(storage: ProjectStorage, project_id: str) -> QualityReport:
    storage.read_project(project_id)
    try:
        data = storage.read_json(project_id, QUALITY_REPORT_PATH)
    except AppError as exc:
        if exc.detail.code == "project_file_not_found":
            raise AppError(
                code="quality_report_not_found",
                message="Quality report has not been generated.",
                status_code=404,
                step="quality_report",
                retryable=True,
                suggested_correction="Export the project to generate a quality report.",
            ) from exc
        raise

    try:
        return QualityReport.model_validate(data)
    except ValidationError as exc:
        raise AppError(
            code="quality_report_invalid",
            message="Quality report metadata is invalid.",
            status_code=500,
            step="quality_report",
            retryable=False,
            suggested_correction="Inspect exports/quality-report.json and regenerate the export.",
            details={"errors": exc.errors(include_url=False, include_input=False)},
        ) from exc


def require_quality_gate(storage: ProjectStorage, project_id: str, *, config_dir: Path) -> QualityReport:
    report = generate_quality_report(storage, project_id, config_dir=config_dir)
    if report.passed:
        return report

    raise AppError(
        code="quality_gate_failed",
        message="Export quality checks did not pass.",
        status_code=409,
        step="quality_gate",
        retryable=True,
        suggested_correction="Fix the failed quality checks and retry export.",
        details={"failed_checks": report.errors},
    )


def mark_project_exported(storage: ProjectStorage, project_id: str) -> None:
    project = storage.read_project(project_id)
    next_project = project.model_copy(deep=True)
    next_project.status = ProjectStatus.EXPORTED
    next_project.current_step = "exported"
    next_project.updated_at = utc_now()
    stale_artifacts = dict(next_project.stale_artifacts)
    stale_artifacts.pop("render", None)
    stale_artifacts.pop("export", None)
    next_project.stale_artifacts = stale_artifacts
    storage.write_json(project.id, PROJECT_METADATA_FILE, next_project)

