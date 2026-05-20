from __future__ import annotations

import re
from pathlib import Path, PurePosixPath


PROJECT_SUBDIRECTORIES: tuple[str, ...] = (
    "assets",
    "metadata",
    "script",
    "storyboard",
    "audio",
    "subtitles",
    "renders",
    "exports",
    "logs",
)

PROJECT_METADATA_FILE = "project.json"

_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


def validate_identifier_value(value: str, field_name: str = "identifier") -> str:
    if not isinstance(value, str) or not _SAFE_IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            f"{field_name} must use only letters, numbers, underscores, and hyphens."
        )
    return value


def validate_project_id(project_id: str) -> str:
    return validate_identifier_value(project_id, "project_id")


def validate_relative_project_path_value(value: str, field_name: str = "path") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty relative path.")
    if "\\" in value or ":" in value:
        raise ValueError(f"{field_name} must use POSIX-style relative paths.")

    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must stay inside the project directory.")
    if any(part in {"", "."} for part in path.parts):
        raise ValueError(f"{field_name} contains an invalid path segment.")
    return path.as_posix()


def resolve_projects_root(projects_root: Path) -> Path:
    return Path(projects_root).expanduser().resolve()


def project_dir(projects_root: Path, project_id: str) -> Path:
    safe_project_id = validate_project_id(project_id)
    root = resolve_projects_root(projects_root)
    candidate = (root / safe_project_id).resolve()
    _ensure_within_root(root, candidate)
    return candidate


def project_json_path(projects_root: Path, project_id: str) -> Path:
    return project_dir(projects_root, project_id) / PROJECT_METADATA_FILE


def project_subdir(projects_root: Path, project_id: str, name: str) -> Path:
    if name not in PROJECT_SUBDIRECTORIES:
        raise ValueError(f"Unsupported project subdirectory: {name}")
    return project_dir(projects_root, project_id) / name


def project_relative_path(projects_root: Path, project_id: str, relative_path: str) -> Path:
    normalized = validate_relative_project_path_value(relative_path)
    root = project_dir(projects_root, project_id)
    candidate = (root / normalized).resolve()
    _ensure_within_root(root, candidate)
    return candidate


def _ensure_within_root(root: Path, candidate: Path) -> None:
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Resolved path escapes the configured projects root.") from exc
