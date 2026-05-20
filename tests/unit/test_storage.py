from pathlib import Path

import pytest

from auto_image.shared.errors import AppError
from auto_image.shared.paths import PROJECT_METADATA_FILE, PROJECT_SUBDIRECTORIES, project_dir
from auto_image.shared.storage import ProjectStorage


def test_create_project_writes_project_json_and_directory_skeleton(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")

    project = storage.create_project(name="Demo")
    project_path = project_dir(tmp_path / "projects", project.id)

    assert (project_path / PROJECT_METADATA_FILE).exists()
    for subdirectory in PROJECT_SUBDIRECTORIES:
        assert (project_path / subdirectory).is_dir()

    saved = storage.read_project(project.id)
    assert saved.id == project.id
    assert saved.schema_version == "1.0"


def test_list_projects_scans_project_json_from_disk(tmp_path: Path) -> None:
    first_storage = ProjectStorage(tmp_path / "projects")
    project = first_storage.create_project(name="Disk backed")

    second_storage = ProjectStorage(tmp_path / "projects")

    assert [item.id for item in second_storage.list_projects()] == [project.id]


def test_write_json_replaces_existing_file_without_temp_artifacts(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    project = storage.create_project(name="Demo")

    storage.write_json(project.id, "metadata/custom.json", {"version": 1})
    storage.write_json(project.id, "metadata/custom.json", {"version": 2})

    assert storage.read_json(project.id, "metadata/custom.json") == {"version": 2}
    project_path = project_dir(tmp_path / "projects", project.id)
    assert not list((project_path / "metadata").glob("*.tmp"))


def test_storage_rejects_unsafe_project_ids_and_paths(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")

    with pytest.raises(AppError) as project_error:
        storage.read_project("../escape")
    assert project_error.value.detail.code == "invalid_project_id"

    project = storage.create_project(name="Demo")
    with pytest.raises(AppError) as path_error:
        storage.write_json(project.id, "../outside.json", {})
    assert path_error.value.detail.code == "invalid_project_path"


def test_read_project_reports_corrupted_json_without_absolute_path(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    project = storage.create_project(name="Demo")
    project_path = project_dir(tmp_path / "projects", project.id)
    (project_path / PROJECT_METADATA_FILE).write_text("{not-json", encoding="utf-8")

    with pytest.raises(AppError) as error:
        storage.read_project(project.id)

    assert error.value.detail.code == "project_metadata_invalid"
    assert str(tmp_path) not in error.value.detail.message
