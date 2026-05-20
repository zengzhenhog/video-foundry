from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import ValidationError

from video_foundry.shared.errors import AppError
from video_foundry.shared.paths import PROJECT_METADATA_FILE
from video_foundry.shared.schemas import (
    Asset,
    AssetStatusSummary,
    BackgroundMusic,
    Project,
    ProjectDetail,
    ProjectStatus,
    VoiceConfig,
    utc_now,
)
from video_foundry.shared.storage import ProjectStorage


ASSET_METADATA_PATH = "metadata/asset.json"
MAX_IMAGE_BYTES = 20 * 1024 * 1024
PREVIEW_RELATIVE_PATH = "assets/preview.jpg"
PREVIEW_MAX_SIZE = (1280, 1280)
IMAGE_FORMAT_EXTENSIONS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}
DOWNSTREAM_ARTIFACT_PATHS = {
    "script": "script/script.json",
    "storyboard": "storyboard/storyboard.json",
    "voice": "audio/narration.wav",
    "subtitles": "subtitles/subtitles.srt",
    "render": "renders/render-manifest.json",
    "export": "exports/quality-report.json",
}


def read_asset_metadata(storage: ProjectStorage, project_id: str) -> Asset | None:
    try:
        data = storage.read_json(project_id, ASSET_METADATA_PATH)
    except AppError as exc:
        if exc.detail.code == "project_file_not_found":
            return None
        raise

    try:
        return Asset.model_validate(data)
    except ValidationError as exc:
        raise AppError(
            code="asset_metadata_invalid",
            message="Asset metadata is invalid.",
            status_code=500,
            step="asset_storage",
            retryable=False,
            suggested_correction="Inspect metadata/asset.json and restore a valid asset record.",
            details={"errors": exc.errors(include_url=False, include_input=False)},
        ) from exc


def build_project_detail(
    storage: ProjectStorage,
    project: Project,
    *,
    background_music: BackgroundMusic | None = None,
    voice_config: VoiceConfig | None = None,
) -> ProjectDetail:
    asset = read_asset_metadata(storage, project.id)
    return ProjectDetail(
        **project.model_dump(),
        asset=asset,
        background_music=background_music,
        voice_config=voice_config,
        asset_status=summarize_asset_status(
            storage,
            project.id,
            asset=asset,
            background_music=background_music,
        ),
    )


def summarize_asset_status(
    storage: ProjectStorage,
    project_id: str,
    *,
    asset: Asset | None = None,
    background_music: BackgroundMusic | None = None,
) -> AssetStatusSummary:
    if asset is None:
        asset = read_asset_metadata(storage, project_id)

    has_original_image = bool(
        asset
        and asset.image_original_path
        and storage.project_file_exists(project_id, asset.image_original_path)
    )
    has_preview_image = bool(
        asset
        and asset.image_preview_path
        and storage.project_file_exists(project_id, asset.image_preview_path)
    )
    has_source_url = bool(asset and asset.source_url and asset.source_url.strip())
    has_credit = bool(asset and asset.credit.strip())
    has_description = bool(asset and asset.description.strip())
    has_background_music = bool(
        background_music
        and background_music.file_path
        and storage.project_file_exists(project_id, background_music.file_path)
    )

    return AssetStatusSummary(
        has_original_image=has_original_image,
        has_preview_image=has_preview_image,
        has_source_url=has_source_url,
        has_credit=has_credit,
        has_description=has_description,
        has_background_music=has_background_music,
        ready_for_script=all(
            [
                has_original_image,
                has_preview_image,
                has_source_url,
                has_credit,
                has_description,
            ]
        ),
    )


def save_image_asset(
    storage: ProjectStorage,
    project: Project,
    *,
    original_filename: str,
    content: bytes,
    config_dir: Path,
) -> Asset:
    if not content:
        raise AppError(
            code="empty_image_upload",
            message="Uploaded image file is empty.",
            status_code=400,
            step="asset_upload",
            retryable=True,
            suggested_correction="Choose a non-empty JPEG, PNG, or WebP file.",
        )
    if len(content) > MAX_IMAGE_BYTES:
        raise AppError(
            code="image_too_large",
            message="Uploaded image exceeds the maximum allowed size.",
            status_code=413,
            step="asset_upload",
            retryable=True,
            suggested_correction="Upload an image smaller than 20 MB.",
            details={"max_bytes": MAX_IMAGE_BYTES},
        )

    image, image_format = _decode_image(content)
    width, height = image.size
    _validate_image_dimensions(width, height, project=project, config_dir=config_dir)

    extension = IMAGE_FORMAT_EXTENSIONS[image_format]
    original_relative_path = f"assets/original.{extension}"
    storage.write_bytes(project.id, original_relative_path, content)
    _remove_other_originals(storage, project.id, keep_relative_path=original_relative_path)

    preview_bytes = _build_preview_bytes(image)
    storage.write_bytes(project.id, PREVIEW_RELATIVE_PATH, preview_bytes)

    existing = read_asset_metadata(storage, project.id)
    previous_sha = existing.sha256 if existing else None
    now = utc_now()
    asset = Asset(
        project_id=project.id,
        title=existing.title if existing else "",
        source_url=existing.source_url if existing else None,
        original_filename=_safe_filename(original_filename),
        image_original_path=original_relative_path,
        image_preview_path=PREVIEW_RELATIVE_PATH,
        image_format=image_format.lower(),
        description=existing.description if existing else "",
        credit=existing.credit if existing else "",
        width=width,
        height=height,
        sha256=hashlib.sha256(content).hexdigest(),
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
    storage.write_json(project.id, ASSET_METADATA_PATH, asset)
    refresh_project_after_asset_change(
        storage,
        project,
        asset,
        upstream_changed=previous_sha != asset.sha256,
    )
    return asset


def save_asset_text(
    storage: ProjectStorage,
    project: Project,
    *,
    title: str,
    description: str,
    source_url: str | None,
    credit: str,
) -> Asset:
    existing = read_asset_metadata(storage, project.id)
    now = utc_now()
    normalized_title = title.strip()
    normalized_description = description.strip()
    normalized_source_url = source_url.strip() if source_url and source_url.strip() else None
    normalized_credit = credit.strip()
    previous_values = (
        existing.title if existing else "",
        existing.description if existing else "",
        existing.source_url if existing else None,
        existing.credit if existing else "",
    )

    asset = Asset(
        project_id=project.id,
        title=normalized_title,
        source_url=normalized_source_url,
        original_filename=existing.original_filename if existing else None,
        image_original_path=existing.image_original_path if existing else None,
        image_preview_path=existing.image_preview_path if existing else None,
        image_format=existing.image_format if existing else None,
        description=normalized_description,
        credit=normalized_credit,
        width=existing.width if existing else None,
        height=existing.height if existing else None,
        sha256=existing.sha256 if existing else None,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
    storage.write_json(project.id, ASSET_METADATA_PATH, asset)
    refresh_project_after_asset_change(
        storage,
        project,
        asset,
        upstream_changed=previous_values
        != (
            asset.title,
            asset.description,
            asset.source_url,
            asset.credit,
        ),
    )
    return asset


def refresh_project_after_asset_change(
    storage: ProjectStorage,
    project: Project,
    asset: Asset,
    *,
    upstream_changed: bool,
) -> Project:
    status = summarize_asset_status(storage, project.id, asset=asset)
    next_project = project.model_copy(deep=True)
    next_project.status = ProjectStatus.ASSET_READY if status.ready_for_script else ProjectStatus.DRAFT
    next_project.current_step = "assets_ready" if status.ready_for_script else "asset_collection"
    next_project.updated_at = utc_now()

    if upstream_changed:
        stale_artifacts = dict(next_project.stale_artifacts)
        for artifact, relative_path in DOWNSTREAM_ARTIFACT_PATHS.items():
            if storage.project_file_exists(project.id, relative_path):
                stale_artifacts[artifact] = True
        next_project.stale_artifacts = stale_artifacts

    storage.write_json(project.id, PROJECT_METADATA_FILE, next_project)
    return next_project


def _decode_image(content: bytes) -> tuple[Image.Image, str]:
    try:
        with Image.open(io.BytesIO(content)) as opened:
            image_format = opened.format
            if image_format not in IMAGE_FORMAT_EXTENSIONS:
                raise AppError(
                    code="unsupported_image_format",
                    message="Uploaded image format is not supported.",
                    status_code=415,
                    step="asset_upload",
                    retryable=True,
                    suggested_correction="Upload a JPEG, PNG, or WebP image.",
                    details={"detected_format": image_format},
                )
            opened.load()
            return ImageOps.exif_transpose(opened).copy(), image_format
    except UnidentifiedImageError as exc:
        raise AppError(
            code="invalid_image_file",
            message="Uploaded file could not be parsed as an image.",
            status_code=400,
            step="asset_upload",
            retryable=True,
            suggested_correction="Upload a valid JPEG, PNG, or WebP image.",
        ) from exc
    except OSError as exc:
        raise AppError(
            code="invalid_image_file",
            message="Uploaded file could not be parsed as an image.",
            status_code=400,
            step="asset_upload",
            retryable=True,
            suggested_correction="Upload a valid JPEG, PNG, or WebP image.",
        ) from exc


def _build_preview_bytes(image: Image.Image) -> bytes:
    preview = _to_rgb_image(image)
    preview.thumbnail(PREVIEW_MAX_SIZE, Image.Resampling.LANCZOS)
    output = io.BytesIO()
    preview.save(output, format="JPEG", quality=88, optimize=True)
    return output.getvalue()


def _to_rgb_image(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _validate_image_dimensions(
    width: int,
    height: int,
    *,
    project: Project,
    config_dir: Path,
) -> None:
    required_width, required_height = _required_render_size(project.formats, config_dir)
    if width < required_width or height < required_height:
        raise AppError(
            code="image_too_small",
            message="Uploaded image is smaller than the required render preset size.",
            status_code=422,
            step="asset_upload",
            retryable=True,
            suggested_correction="Upload a higher-resolution image for the selected output format.",
            details={
                "width": width,
                "height": height,
                "required_width": required_width,
                "required_height": required_height,
                "formats": project.formats,
            },
        )


def _required_render_size(formats: list[str], config_dir: Path) -> tuple[int, int]:
    presets = _load_render_presets(config_dir)
    required_width = 0
    required_height = 0
    for format_name in formats:
        preset = presets.get(format_name)
        if not isinstance(preset, dict):
            raise AppError(
                code="render_preset_missing",
                message="Render preset for the selected project format was not found.",
                status_code=500,
                step="asset_upload",
                retryable=False,
                suggested_correction="Add the missing render preset before uploading assets.",
                details={"format": format_name},
            )
        try:
            required_width = max(required_width, int(preset["width"]))
            required_height = max(required_height, int(preset["height"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError(
                code="render_preset_invalid",
                message="Render preset dimensions are invalid.",
                status_code=500,
                step="asset_upload",
                retryable=False,
                suggested_correction="Fix config/render-presets.json.",
                details={"format": format_name},
            ) from exc
    return required_width, required_height


def _load_render_presets(config_dir: Path) -> dict[str, Any]:
    preset_path = config_dir / "render-presets.json"
    try:
        data = json.loads(preset_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AppError(
            code="render_presets_missing",
            message="Render preset configuration was not found.",
            status_code=500,
            step="asset_upload",
            retryable=False,
            suggested_correction="Restore config/render-presets.json.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise AppError(
            code="render_presets_invalid",
            message="Render preset configuration is invalid JSON.",
            status_code=500,
            step="asset_upload",
            retryable=False,
            suggested_correction="Fix config/render-presets.json.",
        ) from exc
    if not isinstance(data, dict):
        raise AppError(
            code="render_presets_invalid",
            message="Render preset configuration must contain an object.",
            status_code=500,
            step="asset_upload",
            retryable=False,
            suggested_correction="Fix config/render-presets.json.",
        )
    return data


def _remove_other_originals(
    storage: ProjectStorage,
    project_id: str,
    *,
    keep_relative_path: str,
) -> None:
    assets_dir = storage.project_path(project_id) / "assets"
    keep_path = storage.resolve_project_path(project_id, keep_relative_path)
    for candidate in assets_dir.glob("original.*"):
        if candidate != keep_path and candidate.is_file():
            candidate.unlink()


def _safe_filename(filename: str) -> str:
    name = Path(filename or "upload").name.strip()
    return name or "upload"

