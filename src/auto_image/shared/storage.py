from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from auto_image.shared.errors import AppError
from auto_image.shared.paths import (
    PROJECT_METADATA_FILE,
    PROJECT_SUBDIRECTORIES,
    project_dir,
    project_json_path,
    project_relative_path,
    validate_project_id,
    validate_relative_project_path_value,
)
from auto_image.shared.schemas import DEFAULT_FORMATS, Project, utc_now


class ProjectStorage:
    def __init__(self, projects_root: Path) -> None:
        self.projects_root = Path(projects_root)

    def create_project(
        self,
        *,
        name: str,
        target_language: str = "zh-CN",
        target_duration_sec: float = 60,
        formats: list[str] | None = None,
    ) -> Project:
        self.projects_root.mkdir(parents=True, exist_ok=True)
        project = self._new_project(
            name=name,
            target_language=target_language,
            target_duration_sec=target_duration_sec,
            formats=formats or list(DEFAULT_FORMATS),
        )
        self.ensure_project_skeleton(project.id)
        self.write_json(project.id, PROJECT_METADATA_FILE, project)
        return project

    def ensure_project_skeleton(self, project_id: str) -> Path:
        project_path = self._project_dir_or_error(project_id)
        project_path.mkdir(parents=True, exist_ok=True)
        for subdirectory in PROJECT_SUBDIRECTORIES:
            (project_path / subdirectory).mkdir(parents=True, exist_ok=True)
        return project_path

    def read_project(self, project_id: str) -> Project:
        data = self.read_json(project_id, PROJECT_METADATA_FILE)
        try:
            return Project.model_validate(data)
        except ValidationError as exc:
            raise AppError(
                code="project_metadata_invalid",
                message="Project metadata is invalid.",
                status_code=500,
                step="project_storage",
                retryable=False,
                suggested_correction="Inspect project.json and restore a valid project record.",
                details={"errors": exc.errors(include_url=False, include_input=False)},
            ) from exc

    def list_projects(self) -> list[Project]:
        if not self.projects_root.exists():
            return []

        projects: list[Project] = []
        for project_path in sorted(self.projects_root.iterdir(), key=lambda item: item.name):
            if not project_path.is_dir():
                continue
            metadata_path = project_path / PROJECT_METADATA_FILE
            if not metadata_path.exists():
                continue
            projects.append(self.read_project(project_path.name))
        return sorted(projects, key=lambda project: project.updated_at, reverse=True)

    def write_json(self, project_id: str, relative_path: str, data: BaseModel | dict) -> Path:
        target_path = self._relative_path_or_error(project_id, relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, BaseModel):
            payload = data.model_dump(mode="json")
        else:
            payload = data

        temporary_path = target_path.with_name(f".{target_path.name}.{uuid4().hex}.tmp")
        try:
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(target_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        return target_path

    def read_json(self, project_id: str, relative_path: str) -> dict:
        target_path = self._relative_path_or_error(project_id, relative_path)
        if not target_path.exists():
            raise AppError(
                code="project_not_found" if relative_path == PROJECT_METADATA_FILE else "project_file_not_found",
                message="Project metadata was not found."
                if relative_path == PROJECT_METADATA_FILE
                else "Project file was not found.",
                status_code=404,
                step="project_storage",
                retryable=False,
                suggested_correction="Create the project before reading it.",
            )

        try:
            data = json.loads(target_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AppError(
                code="project_metadata_invalid",
                message="Project metadata JSON is corrupted."
                if relative_path == PROJECT_METADATA_FILE
                else "Project JSON file is corrupted.",
                status_code=500,
                step="project_storage",
                retryable=False,
                suggested_correction="Restore the JSON file from a valid backup or recreate the project.",
            ) from exc

        if not isinstance(data, dict):
            raise AppError(
                code="project_metadata_invalid",
                message="Project JSON must contain an object.",
                status_code=500,
                step="project_storage",
                retryable=False,
                suggested_correction="Replace the JSON file with an object payload.",
            )
        return data

    def _new_project(
        self,
        *,
        name: str,
        target_language: str,
        target_duration_sec: float,
        formats: list[str],
    ) -> Project:
        now = utc_now()
        for _ in range(10):
            project_id = f"prj_{uuid4().hex[:16]}"
            if not project_json_path(self.projects_root, project_id).exists():
                return Project(
                    id=project_id,
                    name=name,
                    target_language=target_language,
                    target_duration_sec=target_duration_sec,
                    formats=formats,
                    created_at=now,
                    updated_at=now,
                )
        raise AppError(
            code="project_id_collision",
            message="Could not allocate a unique project id.",
            status_code=500,
            step="project_storage",
            retryable=True,
            suggested_correction="Retry project creation.",
        )

    def _project_dir_or_error(self, project_id: str) -> Path:
        try:
            validate_project_id(project_id)
            return project_dir(self.projects_root, project_id)
        except ValueError as exc:
            raise AppError(
                code="invalid_project_id",
                message="Project id is invalid.",
                status_code=422,
                step="project_storage",
                retryable=False,
                suggested_correction="Use only letters, numbers, underscores, and hyphens.",
            ) from exc

    def _relative_path_or_error(self, project_id: str, relative_path: str) -> Path:
        self._project_dir_or_error(project_id)
        try:
            validate_relative_project_path_value(relative_path)
            return project_relative_path(self.projects_root, project_id, relative_path)
        except ValueError as exc:
            raise AppError(
                code="invalid_project_path",
                message="Project path is invalid.",
                status_code=422,
                step="project_storage",
                retryable=False,
                suggested_correction="Use a relative path inside the project directory.",
            ) from exc
