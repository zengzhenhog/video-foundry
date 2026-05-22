from __future__ import annotations

from collections.abc import Iterator
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from video_foundry.api.dependencies import get_project_storage
from video_foundry.api.main import create_app
from video_foundry.jobs.runner import JobRunResult
from video_foundry.shared.errors import AppError
from video_foundry.shared.storage import ProjectStorage
from video_foundry.sources.nasa_api import NasaSearchResult


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[TestClient, ProjectStorage]]:
    app = create_app()
    storage = ProjectStorage(tmp_path / "projects")
    app.dependency_overrides[get_project_storage] = lambda: storage

    with TestClient(app) as test_client:
        yield test_client, storage

    app.dependency_overrides.clear()


def test_nasa_import_creates_asset_ready_project(
    client: tuple[TestClient, ProjectStorage],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, storage = client

    class FakeNasaClient:
        def resolve_image_url(self, _result: NasaSearchResult) -> str:
            return "https://example.test/full.jpg"

        def download_image(self, _image_url: str) -> bytes:
            return _image_bytes(size=(1080, 1920))

    monkeypatch.setattr("video_foundry.api.routes.imports.build_nasa_client", lambda: FakeNasaClient())

    response = test_client.post(
        "/api/imports/nasa/projects",
        json={
            "result": {
                "nasa_id": "PIA00001",
                "title": "NASA Moon",
                "description": "Official NASA source copy.",
                "source_url": "https://images.nasa.gov/details/PIA00001",
                "credit": "NASA / JPL",
                "image_url": "https://example.test/thumb.jpg",
                "thumbnail_url": "https://example.test/thumb.jpg",
                "asset_manifest_url": "https://example.test/manifest",
                "center": "JPL",
                "date_created": "2026-01-01T00:00:00Z",
            },
            "target_language": "zh-CN",
            "target_duration_sec": 30,
            "formats": ["vertical_1080x1920"],
        },
    )

    assert response.status_code == 201
    detail = response.json()
    assert detail["status"] == "asset_ready"
    assert detail["asset"]["source_url"] == "https://images.nasa.gov/details/PIA00001"
    assert detail["asset"]["credit"] == "NASA / JPL"
    assert detail["metadata"]["source_import"]["provider"] == "nasa"
    assert (storage.projects_root / detail["id"] / "metadata" / "asset.json").exists()


def test_batch_queue_api_continues_after_failed_project(
    client: tuple[TestClient, ProjectStorage],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, _storage = client
    first = test_client.post("/api/projects", json={"name": "Fail me"}).json()
    second = test_client.post("/api/projects", json={"name": "Succeed me"}).json()

    def fake_run_generate_all(storage: ProjectStorage, project_id: str, *, config_dir, progress):
        progress(0.5, "Testing batch.")
        if project_id == first["id"]:
            raise AppError(
                code="forced_failure",
                message="Forced batch failure.",
                status_code=409,
                step="test_batch",
                retryable=True,
            )
        return JobRunResult(output_paths=["exports/final_vertical_1080x1920.mp4"], summary="Done.")

    monkeypatch.setattr("video_foundry.api.routes.pipeline.run_generate_all", fake_run_generate_all)

    response = test_client.post(
        "/api/batch/queue",
        json={"project_ids": [first["id"], second["id"]], "action": "generate_all", "max_attempts": 1},
    )

    assert response.status_code == 202
    queue_response = test_client.get("/api/batch/queue")
    items = queue_response.json()["items"]
    statuses = {item["project_id"]: item["status"] for item in items}
    assert statuses[first["id"]] == "failed"
    assert statuses[second["id"]] == "succeeded"


def test_project_index_and_publish_placeholder_api(client: tuple[TestClient, ProjectStorage]) -> None:
    test_client, _storage = client
    project = test_client.post("/api/projects", json={"name": "Indexed project"}).json()

    rebuild = test_client.post("/api/index/rebuild")
    assert rebuild.status_code == 200
    assert rebuild.json()["indexed"] == 1

    indexed = test_client.get("/api/index/projects", params={"query": "indexed"}).json()
    assert indexed["projects"][0]["id"] == project["id"]

    publish = test_client.post(f"/api/projects/{project['id']}/publish/prepare", json={"platform": "youtube"})
    assert publish.status_code == 200
    assert publish.json()["ready"] is False


def _image_bytes(*, size: tuple[int, int]) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, color=(44, 84, 122)).save(output, format="JPEG")
    return output.getvalue()
