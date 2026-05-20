from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from auto_image.api.dependencies import get_project_storage
from auto_image.api.main import create_app
from auto_image.shared.paths import PROJECT_METADATA_FILE, PROJECT_SUBDIRECTORIES
from auto_image.shared.storage import ProjectStorage


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[TestClient, ProjectStorage]]:
    app = create_app()
    storage = ProjectStorage(tmp_path / "projects")
    app.dependency_overrides[get_project_storage] = lambda: storage

    with TestClient(app) as test_client:
        yield test_client, storage

    app.dependency_overrides.clear()


def test_create_list_and_read_project_api(client: tuple[TestClient, ProjectStorage]) -> None:
    test_client, storage = client

    create_response = test_client.post(
        "/api/projects",
        json={"name": "Nebula Short", "target_language": "en-US", "target_duration_sec": 45},
    )

    assert create_response.status_code == 201
    project = create_response.json()
    assert project["schema_version"] == "1.0"
    assert project["status"] == "draft"
    assert project["target_language"] == "en-US"

    project_path = storage.projects_root / project["id"]
    assert (project_path / PROJECT_METADATA_FILE).exists()
    for subdirectory in PROJECT_SUBDIRECTORIES:
        assert (project_path / subdirectory).is_dir()

    list_response = test_client.get("/api/projects")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["projects"]] == [project["id"]]

    read_response = test_client.get(f"/api/projects/{project['id']}")
    assert read_response.status_code == 200
    assert read_response.json()["id"] == project["id"]


def test_project_api_not_found_error_is_structured(client: tuple[TestClient, ProjectStorage]) -> None:
    test_client, _storage = client

    response = test_client.get("/api/projects/missing_project")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"
    assert "traceback" not in response.text.lower()


def test_project_api_invalid_id_error_is_structured(client: tuple[TestClient, ProjectStorage]) -> None:
    test_client, _storage = client

    response = test_client.get("/api/projects/bad..id")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_project_id"


def test_project_api_validation_error_is_structured(client: tuple[TestClient, ProjectStorage]) -> None:
    test_client, _storage = client

    response = test_client.post("/api/projects", json={"name": "", "target_duration_sec": -1})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_project_api_reports_corrupted_json(client: tuple[TestClient, ProjectStorage]) -> None:
    test_client, storage = client
    project = test_client.post("/api/projects", json={"name": "Broken"}).json()
    (storage.projects_root / project["id"] / PROJECT_METADATA_FILE).write_text("{broken", encoding="utf-8")

    response = test_client.get(f"/api/projects/{project['id']}")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "project_metadata_invalid"
    assert str(storage.projects_root) not in response.text
