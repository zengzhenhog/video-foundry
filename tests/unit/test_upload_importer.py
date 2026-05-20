from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image

from video_foundry.shared.schemas import ProjectStatus
from video_foundry.shared.storage import ProjectStorage
from video_foundry.sources.upload_importer import save_asset_text, save_image_asset


def test_image_upload_writes_original_preview_and_asset_metadata(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    project = storage.create_project(name="Asset project")
    image_bytes = _image_bytes(size=(1080, 1920))

    asset = save_image_asset(
        storage,
        project,
        original_filename="source.jpg",
        content=image_bytes,
        config_dir=Path("config"),
    )

    assert (storage.projects_root / project.id / "assets" / "original.jpg").exists()
    preview_path = storage.projects_root / project.id / "assets" / "preview.jpg"
    assert preview_path.exists()
    assert (storage.projects_root / project.id / "metadata" / "asset.json").exists()
    assert asset.sha256 == hashlib.sha256(image_bytes).hexdigest()
    assert asset.width == 1080
    assert asset.height == 1920

    with Image.open(preview_path) as preview:
        assert preview.format == "JPEG"
        assert preview.width <= 1280
        assert preview.height <= 1280


def test_missing_credit_or_source_keeps_project_in_draft(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    project = storage.create_project(name="Asset project")
    image_bytes = _image_bytes(size=(1080, 1920))
    save_image_asset(
        storage,
        project,
        original_filename="source.jpg",
        content=image_bytes,
        config_dir=Path("config"),
    )

    project_after_image = storage.read_project(project.id)
    asset = save_asset_text(
        storage,
        project_after_image,
        title="Title",
        description="Useful copy",
        source_url="https://example.test/source",
        credit="",
    )

    assert asset.credit == ""
    assert storage.read_project(project.id).status is ProjectStatus.DRAFT


def test_complete_asset_text_marks_project_asset_ready(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    project = storage.create_project(name="Asset project")
    save_image_asset(
        storage,
        project,
        original_filename="source.jpg",
        content=_image_bytes(size=(1080, 1920)),
        config_dir=Path("config"),
    )

    project_after_image = storage.read_project(project.id)
    save_asset_text(
        storage,
        project_after_image,
        title="Title",
        description="Useful copy",
        source_url="https://example.test/source",
        credit="Example Observatory / Public Domain",
    )

    assert storage.read_project(project.id).status is ProjectStatus.ASSET_READY


def _image_bytes(*, size: tuple[int, int]) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, color=(36, 92, 138)).save(output, format="JPEG")
    return output.getvalue()

