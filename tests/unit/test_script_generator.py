from pathlib import Path

import pytest

from video_foundry.ai.base import ScriptGenerationInput
from video_foundry.ai.mock_provider import MockScriptProvider
from video_foundry.ai.script_generator import (
    SCRIPT_JSON_PATH,
    SCRIPT_MARKDOWN_PATH,
    approve_script,
    ensure_script_approved,
    generate_project_script,
    save_project_script,
    validate_provider_script_output,
)
from video_foundry.shared.errors import AppError
from video_foundry.shared.schemas import Asset, Project, ProjectStatus
from video_foundry.shared.storage import ProjectStorage
from video_foundry.sources.upload_importer import ASSET_METADATA_PATH


def test_mock_script_provider_is_deterministic() -> None:
    script_input = _script_input()
    provider = MockScriptProvider()

    first = provider.generate_script(script_input)
    second = provider.generate_script(script_input)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.approved is False
    assert "Grounding" in first.review_notes


def test_generate_script_requires_complete_grounded_asset(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    project = storage.create_project(name="Missing credit")
    _write_asset(
        storage,
        project,
        description="Official description.",
        source_url="https://example.test/source",
        credit="",
    )

    with pytest.raises(AppError) as error:
        generate_project_script(storage, project.id)

    assert error.value.detail.code == "asset_not_ready_for_script"
    assert error.value.detail.details["missing"] == ["credit"]


def test_generate_script_writes_json_markdown_and_status(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    project = storage.create_project(name="Scriptable", target_duration_sec=30)
    _write_asset(storage, project)

    script = generate_project_script(storage, project.id)

    assert script.approved is False
    assert storage.project_file_exists(project.id, SCRIPT_JSON_PATH)
    assert storage.project_file_exists(project.id, SCRIPT_MARKDOWN_PATH)
    assert storage.read_project(project.id).status is ProjectStatus.SCRIPT_READY
    markdown = storage.resolve_project_path(project.id, SCRIPT_MARKDOWN_PATH).read_text(encoding="utf-8")
    assert "## Review Notes" in markdown
    assert "Official source description." in markdown


def test_save_approved_script_revokes_approval(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    project = storage.create_project(name="Approval", target_duration_sec=20)
    _write_asset(storage, project)
    generate_project_script(storage, project.id)
    approved = approve_script(storage, project.id)

    assert approved.approved is True
    assert storage.read_project(project.id).status is ProjectStatus.SCRIPT_APPROVED

    changed = approved.model_copy(update={"narration": "Edited narration."}, deep=True)
    saved = save_project_script(storage, project.id, changed)

    assert saved.approved is False
    assert saved.approved_at is None
    assert storage.read_project(project.id).status is ProjectStatus.SCRIPT_READY
    assert storage.read_json(project.id, SCRIPT_JSON_PATH)["narration"] == "Edited narration."


def test_unapproved_script_blocks_downstream_gate(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    project = storage.create_project(name="Gate")
    _write_asset(storage, project)
    generate_project_script(storage, project.id)

    with pytest.raises(AppError) as error:
        ensure_script_approved(storage, project.id, step="voice_generation")

    assert error.value.detail.code == "script_not_approved"
    assert error.value.detail.step == "voice_generation"


def test_provider_output_requires_grounding_notes_and_known_schema() -> None:
    script_input = _script_input()
    valid = MockScriptProvider().generate_script(script_input)
    missing_grounding = valid.model_dump(mode="json")
    missing_grounding["review_notes"] = ""

    with pytest.raises(AppError) as grounding_error:
        validate_provider_script_output(missing_grounding, script_input)

    assert grounding_error.value.detail.code == "script_grounding_missing"

    unsupported_fact = valid.model_dump(mode="json")
    unsupported_fact["distance_from_earth"] = "42 light years"

    with pytest.raises(AppError) as schema_error:
        validate_provider_script_output(unsupported_fact, script_input)

    assert schema_error.value.detail.code == "script_provider_output_invalid"


def _script_input() -> ScriptGenerationInput:
    return ScriptGenerationInput(
        project_id="prj_123",
        title="Solar loop",
        description="Official source description.",
        source_url="https://example.test/source",
        credit="Example Observatory",
        target_language="zh-CN",
        target_duration_sec=30,
    )


def _write_asset(
    storage: ProjectStorage,
    project: Project,
    *,
    description: str = "Official source description.",
    source_url: str | None = "https://example.test/source",
    credit: str = "Example Observatory",
) -> None:
    storage.write_bytes(project.id, "assets/original.png", b"image")
    storage.write_bytes(project.id, "assets/preview.jpg", b"preview")
    storage.write_json(
        project.id,
        ASSET_METADATA_PATH,
        Asset(
            project_id=project.id,
            title="Solar loop",
            source_url=source_url,
            image_original_path="assets/original.png",
            image_preview_path="assets/preview.jpg",
            image_format="png",
            description=description,
            credit=credit,
            width=1080,
            height=1920,
            sha256="a" * 64,
        ),
    )
