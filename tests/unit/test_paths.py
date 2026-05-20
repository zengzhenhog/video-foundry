from pathlib import Path

import pytest

from video_foundry.shared.paths import (
    PROJECT_METADATA_FILE,
    PROJECT_SUBDIRECTORIES,
    project_dir,
    project_json_path,
    project_relative_path,
    project_subdir,
    validate_project_id,
    validate_relative_project_path_value,
)


def test_project_dir_resolves_under_projects_root(tmp_path: Path) -> None:
    root = tmp_path / "projects"

    resolved = project_dir(root, "project_1")

    assert resolved == root.resolve() / "project_1"


@pytest.mark.parametrize("project_id", ["../escape", "/escape", "bad/name", "bad\\name", ".hidden"])
def test_project_id_rejects_path_traversal(project_id: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        project_dir(tmp_path / "projects", project_id)

    with pytest.raises(ValueError):
        validate_project_id(project_id)


def test_project_json_path_points_to_metadata_file(tmp_path: Path) -> None:
    assert project_json_path(tmp_path / "projects", "project_1").name == PROJECT_METADATA_FILE


def test_project_subdir_accepts_only_known_subdirectories(tmp_path: Path) -> None:
    for subdirectory in PROJECT_SUBDIRECTORIES:
        assert project_subdir(tmp_path / "projects", "project_1", subdirectory).name == subdirectory

    with pytest.raises(ValueError):
        project_subdir(tmp_path / "projects", "project_1", "unknown")


def test_relative_project_path_stays_inside_project(tmp_path: Path) -> None:
    root = tmp_path / "projects"

    resolved = project_relative_path(root, "project_1", "assets/original.jpg")

    assert resolved == root.resolve() / "project_1" / "assets" / "original.jpg"


@pytest.mark.parametrize("relative_path", ["../outside.json", "/outside.json", "assets\\original.jpg", ""])
def test_relative_project_path_rejects_unsafe_paths(relative_path: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        project_relative_path(tmp_path / "projects", "project_1", relative_path)

    with pytest.raises(ValueError):
        validate_relative_project_path_value(relative_path)

