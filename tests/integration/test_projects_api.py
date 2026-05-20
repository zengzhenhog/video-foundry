from collections.abc import Iterator
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from video_foundry.api.dependencies import get_project_storage
from video_foundry.api.main import create_app
from video_foundry.shared.paths import PROJECT_METADATA_FILE, PROJECT_SUBDIRECTORIES
from video_foundry.shared.storage import ProjectStorage


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


def test_asset_upload_flow_persists_metadata_and_status_summary(
    client: tuple[TestClient, ProjectStorage],
) -> None:
    test_client, storage = client
    project = test_client.post("/api/projects", json={"name": "Assets"}).json()
    image_bytes = _image_bytes(size=(1080, 1920))

    image_response = test_client.post(
        f"/api/projects/{project['id']}/assets/image",
        files={"file": ("source.png", image_bytes, "image/png")},
    )

    assert image_response.status_code == 201
    image_asset = image_response.json()
    assert image_asset["image_original_path"] == "assets/original.png"
    assert image_asset["image_preview_path"] == "assets/preview.jpg"
    assert image_asset["width"] == 1080
    assert image_asset["height"] == 1920
    assert (storage.projects_root / project["id"] / "metadata" / "asset.json").exists()

    missing_credit_response = test_client.post(
        f"/api/projects/{project['id']}/assets/text",
        json={
            "title": "Solar loop",
            "description": "A bright coronal loop over the limb.",
            "source_url": "https://example.test/image",
            "credit": "",
        },
    )
    assert missing_credit_response.status_code == 200
    draft_detail = test_client.get(f"/api/projects/{project['id']}").json()
    assert draft_detail["status"] == "draft"
    assert draft_detail["asset_status"]["has_source_url"] is True
    assert draft_detail["asset_status"]["has_credit"] is False
    assert draft_detail["asset_status"]["ready_for_script"] is False

    complete_text_response = test_client.post(
        f"/api/projects/{project['id']}/assets/text",
        json={
            "title": "Solar loop",
            "description": "A bright coronal loop over the limb.",
            "source_url": "https://example.test/image",
            "credit": "Example Observatory / Public Domain",
        },
    )
    assert complete_text_response.status_code == 200

    ready_detail = test_client.get(f"/api/projects/{project['id']}").json()
    assert ready_detail["status"] == "asset_ready"
    assert ready_detail["asset_status"]["ready_for_script"] is True
    assert ready_detail["asset"]["credit"] == "Example Observatory / Public Domain"

    preview_response = test_client.get(f"/api/projects/{project['id']}/assets/preview")
    assert preview_response.status_code == 200
    assert preview_response.headers["content-type"].startswith("image/jpeg")


def test_background_music_upload_is_optional_for_asset_readiness(
    client: tuple[TestClient, ProjectStorage],
) -> None:
    test_client, storage = client
    project = test_client.post("/api/projects", json={"name": "Optional music"}).json()

    test_client.post(
        f"/api/projects/{project['id']}/assets/image",
        files={"file": ("source.jpg", _image_bytes(size=(1080, 1920)), "image/jpeg")},
    )
    test_client.post(
        f"/api/projects/{project['id']}/assets/text",
        json={
            "title": "No music needed",
            "description": "The source image has enough context.",
            "source_url": "https://example.test/image",
            "credit": "Example Observatory",
        },
    )
    detail_without_music = test_client.get(f"/api/projects/{project['id']}").json()
    assert detail_without_music["status"] == "asset_ready"
    assert detail_without_music["asset_status"]["has_background_music"] is False
    assert detail_without_music["asset_status"]["ready_for_script"] is True

    music_response = test_client.post(
        f"/api/projects/{project['id']}/assets/background-music",
        files={"file": ("bed.mp3", b"ID3 audio bytes", "audio/mpeg")},
    )
    assert music_response.status_code == 201
    assert music_response.json()["file_path"] == "audio/background_music.mp3"
    assert (storage.projects_root / project["id"] / "audio" / "background_music.mp3").exists()

    detail_with_music = test_client.get(f"/api/projects/{project['id']}").json()
    assert detail_with_music["asset_status"]["has_background_music"] is True
    assert detail_with_music["background_music"]["original_filename"] == "bed.mp3"


def _image_bytes(*, size: tuple[int, int]) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, color=(42, 80, 112)).save(output, format="PNG")
    return output.getvalue()

