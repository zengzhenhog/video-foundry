from fastapi.testclient import TestClient

from video_foundry.api.main import app


def test_app_imports_and_health_endpoint_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "name": "video-foundry",
        "version": "0.1.0",
        "status": "ok",
    }

