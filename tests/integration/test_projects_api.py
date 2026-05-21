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


def test_script_api_generate_save_and_approve(client: tuple[TestClient, ProjectStorage]) -> None:
    test_client, storage = client
    project = test_client.post(
        "/api/projects",
        json={"name": "Script API", "target_language": "zh-CN", "target_duration_sec": 24},
    ).json()
    test_client.post(
        f"/api/projects/{project['id']}/assets/image",
        files={"file": ("source.png", _image_bytes(size=(1080, 1920)), "image/png")},
    )
    test_client.post(
        f"/api/projects/{project['id']}/assets/text",
        json={
            "title": "Grounded image",
            "description": "Official source description for the image.",
            "source_url": "https://example.test/source",
            "credit": "Example Observatory",
        },
    )

    generate_response = test_client.post(
        f"/api/projects/{project['id']}/script/generate",
        json={"user_draft": "Keep the tone calm."},
    )

    assert generate_response.status_code == 200
    generated = generate_response.json()
    assert generated["approved"] is False
    assert generated["segments"]
    assert generated["review_notes"]
    assert (storage.projects_root / project["id"] / "script" / "script.json").exists()
    assert (storage.projects_root / project["id"] / "script" / "script.md").exists()
    assert test_client.get(f"/api/projects/{project['id']}").json()["status"] == "script_ready"

    read_response = test_client.get(f"/api/projects/{project['id']}/script")
    assert read_response.status_code == 200
    assert read_response.json()["title"] == "Grounded image"

    edited = {
        "language": generated["language"],
        "duration_target_sec": generated["duration_target_sec"],
        "title": generated["title"],
        "narration": "Edited narration grounded in the saved source.",
        "segments": [
            {
                "start_sec": 0,
                "end_sec": 24,
                "text": "Edited narration grounded in the saved source.",
            }
        ],
        "review_notes": "Grounded in the saved description, source URL, credit, and draft.",
    }
    save_response = test_client.put(f"/api/projects/{project['id']}/script", json=edited)
    assert save_response.status_code == 200
    assert save_response.json()["approved"] is False

    approve_response = test_client.post(f"/api/projects/{project['id']}/script/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["approved"] is True
    assert test_client.get(f"/api/projects/{project['id']}").json()["status"] == "script_approved"


def test_script_api_returns_structured_error_before_assets_ready(
    client: tuple[TestClient, ProjectStorage],
) -> None:
    test_client, _storage = client
    project = test_client.post("/api/projects", json={"name": "No assets"}).json()

    response = test_client.post(f"/api/projects/{project['id']}/script/generate", json={})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "asset_not_ready_for_script"
    assert "traceback" not in response.text.lower()


def test_voice_provider_and_preset_endpoints(client: tuple[TestClient, ProjectStorage]) -> None:
    test_client, _storage = client

    providers_response = test_client.get("/api/voice/providers")
    presets_response = test_client.get("/api/voice/presets")

    assert providers_response.status_code == 200
    assert providers_response.json()["providers"][0]["id"] == "mock"
    assert presets_response.status_code == 200
    assert any(preset["id"] == "mock-narrator" for preset in presets_response.json()["presets"])


def test_voice_config_rejects_missing_voice_id(client: tuple[TestClient, ProjectStorage]) -> None:
    test_client, _storage = client
    project = test_client.post("/api/projects", json={"name": "Voice config"}).json()

    response = test_client.put(
        f"/api/projects/{project['id']}/voice/config",
        json={
            "provider": "mock",
            "voice_id": "",
            "language": "zh-CN",
            "speed": 1,
            "volume_gain_db": 0,
            "style": "clear",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_voice_generation_requires_approved_script(client: tuple[TestClient, ProjectStorage]) -> None:
    test_client, _storage = client
    project = _create_project_with_generated_script(test_client, approved=False)
    config_response = _save_mock_voice_config(test_client, project["id"])
    assert config_response.status_code == 200

    response = test_client.post(f"/api/projects/{project['id']}/voice/generate")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "script_not_approved"


def test_voice_api_generates_audio_for_approved_script(
    client: tuple[TestClient, ProjectStorage],
) -> None:
    test_client, storage = client
    project = _create_project_with_generated_script(test_client, approved=True)

    config_response = _save_mock_voice_config(test_client, project["id"])
    assert config_response.status_code == 200
    assert config_response.json()["audio_path"] is None

    generate_response = test_client.post(f"/api/projects/{project['id']}/voice/generate")

    assert generate_response.status_code == 200
    voice_config = generate_response.json()
    assert voice_config["audio_path"] == "audio/narration.wav"
    assert voice_config["duration_sec"] > 0
    assert voice_config["provider_metadata"]["provider"] == "mock"

    project_path = storage.projects_root / project["id"]
    audio_path = project_path / "audio" / "narration.wav"
    voice_json_path = project_path / "audio" / "voice.json"
    assert audio_path.exists()
    assert audio_path.stat().st_size > 44
    assert "api_key" not in voice_json_path.read_text(encoding="utf-8").lower()

    audio_response = test_client.get(f"/api/projects/{project['id']}/voice/audio")
    assert audio_response.status_code == 200
    assert audio_response.headers["content-type"].startswith("audio/wav")
    assert len(audio_response.content) > 44
    assert test_client.get(f"/api/projects/{project['id']}").json()["status"] == "voice_ready"


def test_storyboard_generation_requires_approved_script(
    client: tuple[TestClient, ProjectStorage],
) -> None:
    test_client, _storage = client
    project = _create_project_with_generated_script(test_client, approved=False)

    response = test_client.post(f"/api/projects/{project['id']}/storyboard/generate", json={})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "script_not_approved"


def test_storyboard_api_generates_approves_and_subtitles(
    client: tuple[TestClient, ProjectStorage],
) -> None:
    test_client, storage = client
    project = _create_project_with_generated_script(test_client, approved=True)

    generate_response = test_client.post(f"/api/projects/{project['id']}/storyboard/generate", json={})

    assert generate_response.status_code == 200
    storyboard = generate_response.json()
    assert storyboard["approved"] is False
    assert storyboard["shots"][0]["start_sec"] == 0
    assert (storage.projects_root / project["id"] / "storyboard" / "storyboard.json").exists()
    assert test_client.get(f"/api/projects/{project['id']}").json()["status"] == "storyboard_ready"

    approve_response = test_client.post(f"/api/projects/{project['id']}/storyboard/approve")
    assert approve_response.status_code == 200
    approved = approve_response.json()
    assert approved["approved"] is True
    assert test_client.get(f"/api/projects/{project['id']}").json()["status"] == "storyboard_approved"

    subtitles_response = test_client.post(f"/api/projects/{project['id']}/subtitles/generate")
    assert subtitles_response.status_code == 200
    manifest = subtitles_response.json()
    assert manifest["source"] == "storyboard"
    assert manifest["storyboard_version"] == approved["version"]
    assert (storage.projects_root / project["id"] / "subtitles" / "subtitles.srt").exists()
    assert (storage.projects_root / project["id"] / "subtitles" / "subtitles.vtt").exists()


def test_editing_approved_storyboard_marks_subtitles_stale(
    client: tuple[TestClient, ProjectStorage],
) -> None:
    test_client, storage = client
    project = _create_project_with_generated_script(test_client, approved=True)
    generated = test_client.post(f"/api/projects/{project['id']}/storyboard/generate", json={}).json()
    test_client.post(f"/api/projects/{project['id']}/storyboard/approve")
    subtitles_response = test_client.post(f"/api/projects/{project['id']}/subtitles/generate")
    assert subtitles_response.status_code == 200

    edited = {
        "format": generated["format"],
        "fps": generated["fps"],
        "duration_sec": generated["duration_sec"],
        "safe_area": generated["safe_area"],
        "shots": [
            {
                **shot,
                "caption": f"{shot['caption']} Edited" if index == 0 else shot["caption"],
            }
            for index, shot in enumerate(generated["shots"])
        ],
    }
    save_response = test_client.put(f"/api/projects/{project['id']}/storyboard", json=edited)

    assert save_response.status_code == 200
    detail = test_client.get(f"/api/projects/{project['id']}").json()
    assert detail["status"] == "storyboard_ready"
    assert detail["stale_artifacts"]["subtitles"] is True
    manifest = storage.read_json(project["id"], "subtitles/subtitles.json")
    assert manifest["stale"] is True


def _image_bytes(*, size: tuple[int, int]) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, color=(42, 80, 112)).save(output, format="PNG")
    return output.getvalue()


def _create_project_with_generated_script(test_client: TestClient, *, approved: bool) -> dict:
    project = test_client.post(
        "/api/projects",
        json={"name": "Voice API", "target_language": "zh-CN", "target_duration_sec": 20},
    ).json()
    test_client.post(
        f"/api/projects/{project['id']}/assets/image",
        files={"file": ("source.png", _image_bytes(size=(1080, 1920)), "image/png")},
    )
    test_client.post(
        f"/api/projects/{project['id']}/assets/text",
        json={
            "title": "Voice source",
            "description": "Official source description for voice generation.",
            "source_url": "https://example.test/source",
            "credit": "Example Observatory",
        },
    )
    generate_response = test_client.post(
        f"/api/projects/{project['id']}/script/generate",
        json={"user_draft": None},
    )
    assert generate_response.status_code == 200
    if approved:
        approve_response = test_client.post(f"/api/projects/{project['id']}/script/approve")
        assert approve_response.status_code == 200
    return project


def _save_mock_voice_config(test_client: TestClient, project_id: str):
    return test_client.put(
        f"/api/projects/{project_id}/voice/config",
        json={
            "provider": "mock",
            "voice_id": "mock-narrator",
            "language": "zh-CN",
            "speed": 1,
            "volume_gain_db": 0,
            "style": "clear",
        },
    )

