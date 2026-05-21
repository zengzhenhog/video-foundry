from __future__ import annotations

from pydantic import ValidationError

from video_foundry.ai.script_generator import read_project_script
from video_foundry.audio.background_music import read_background_music_metadata
from video_foundry.renderer.manifest import RENDER_MANIFEST_PATH
from video_foundry.shared.errors import AppError
from video_foundry.shared.schemas import QualityCheck, QualityReport, RenderManifest, Storyboard, utc_now
from video_foundry.shared.storage import ProjectStorage
from video_foundry.sources.upload_importer import read_asset_metadata
from video_foundry.storyboard.planner import read_project_storyboard
from video_foundry.storyboard.validator import RenderPreset, load_render_preset
from video_foundry.subtitles.generator import read_subtitles_manifest
from video_foundry.voice.provider_registry import read_voice_config


DEFAULT_MIN_VIDEO_BYTES = 1
DEFAULT_DURATION_TOLERANCE_SEC = 2.0
DEFAULT_DURATION_TOLERANCE_RATIO = 0.1


def run_quality_checks(
    storage: ProjectStorage,
    project_id: str,
    *,
    config_dir,
    min_video_size_bytes: int = DEFAULT_MIN_VIDEO_BYTES,
    duration_tolerance_sec: float = DEFAULT_DURATION_TOLERANCE_SEC,
    duration_tolerance_ratio: float = DEFAULT_DURATION_TOLERANCE_RATIO,
) -> QualityReport:
    project = storage.read_project(project_id)
    checks: list[QualityCheck] = []

    asset = _read_optional(lambda: read_asset_metadata(storage, project.id))
    script = _read_optional(lambda: read_project_script(storage, project.id))
    storyboard = _read_optional(lambda: read_project_storyboard(storage, project.id))
    subtitles = _read_optional(lambda: read_subtitles_manifest(storage, project.id))
    voice_config = _read_optional(lambda: read_voice_config(storage, project.id))
    background_music = _read_optional(lambda: read_background_music_metadata(storage, project.id))
    manifest = _read_render_manifest(storage, project.id)
    preset = _read_optional(lambda: load_render_preset(config_dir, storyboard.format)) if storyboard else None

    _add_check(
        checks,
        "source_image_exists",
        bool(asset and asset.image_original_path and storage.project_file_exists(project.id, asset.image_original_path)),
        {"path": asset.image_original_path if asset else None},
    )
    _add_check(
        checks,
        "source_hash_recorded",
        bool(asset and asset.sha256 and (manifest is None or manifest.source_image_sha256 == asset.sha256)),
        {
            "asset_hash": asset.sha256 if asset else None,
            "manifest_hash": manifest.source_image_sha256 if manifest else None,
        },
    )
    _add_check(checks, "credit_exists", bool(asset and asset.credit.strip()))
    _add_check(checks, "source_url_exists", bool(asset and asset.source_url and asset.source_url.strip()))
    _add_check(
        checks,
        "description_or_text_exists",
        bool(asset and (asset.description.strip() or asset.title.strip())),
    )
    _add_check(
        checks,
        "script_approved",
        bool(script and script.approved and not project.stale_artifacts.get("script")),
        {"stale": project.stale_artifacts.get("script", False)},
    )
    _add_check(
        checks,
        "storyboard_approved",
        bool(storyboard and storyboard.approved and not project.stale_artifacts.get("storyboard")),
        {"stale": project.stale_artifacts.get("storyboard", False)},
    )
    _add_check(
        checks,
        "crop_coordinates_legal",
        bool(storyboard and _crop_coordinates_legal(storyboard)),
    )
    _add_check(
        checks,
        "max_zoom_legal",
        bool(storyboard and preset and _max_zoom_legal(storyboard, preset)),
        {"max_zoom": preset.max_zoom if preset else None},
    )
    narration_exists = bool(
        voice_config
        and voice_config.audio_path
        and storage.project_file_exists(project.id, voice_config.audio_path)
    )
    _add_check(
        checks,
        "narration_audio_exists",
        narration_exists,
        {"path": voice_config.audio_path if voice_config else None},
    )
    _add_check(
        checks,
        "narration_duration_matches_storyboard",
        bool(
            voice_config
            and voice_config.duration_sec is not None
            and storyboard
            and _duration_matches(
                voice_config.duration_sec,
                storyboard.duration_sec,
                tolerance_sec=duration_tolerance_sec,
                tolerance_ratio=duration_tolerance_ratio,
            )
        ),
        {
            "voice_duration_sec": voice_config.duration_sec if voice_config else None,
            "storyboard_duration_sec": storyboard.duration_sec if storyboard else None,
        },
    )
    _add_check(
        checks,
        "background_music_readable",
        _background_music_readable(storage, project.id, background_music),
        {"path": background_music.file_path if background_music else None, "optional": background_music is None},
    )
    subtitles_exist = bool(
        subtitles
        and storage.project_file_exists(project.id, subtitles.srt_path)
        and storage.project_file_exists(project.id, subtitles.vtt_path)
        and not subtitles.stale
        and not project.stale_artifacts.get("subtitles")
    )
    _add_check(
        checks,
        "subtitles_exist",
        subtitles_exist,
        {
            "srt_path": subtitles.srt_path if subtitles else None,
            "vtt_path": subtitles.vtt_path if subtitles else None,
            "stale": subtitles.stale if subtitles else None,
        },
    )
    _add_check(
        checks,
        "subtitle_safe_area_or_manifest_evidence",
        bool(manifest and _overlay_box_visible(manifest.subtitle_overlay, width=manifest.width, height=manifest.height)),
    )
    _add_check(checks, "render_manifest_exists", manifest is not None, {"path": RENDER_MANIFEST_PATH})
    _add_check(
        checks,
        "render_manifest_proves_visible_credit_overlay",
        bool(
            manifest
            and manifest.credit_text.strip()
            and manifest.final_output_path
            and _overlay_box_visible(manifest.credit_overlay, width=manifest.width, height=manifest.height)
        ),
        {"credit_text": manifest.credit_text if manifest else None},
    )
    _add_check(
        checks,
        "render_manifest_uses_deterministic_source_rules",
        bool(manifest and any("No generative image" in rule for rule in manifest.deterministic_rules)),
    )
    final_output_path = manifest.final_output_path if manifest and manifest.final_output_path else None
    _add_check(
        checks,
        "export_mp4_exists_and_nonempty",
        bool(final_output_path and _file_size(storage, project.id, final_output_path) > min_video_size_bytes),
        {
            "path": final_output_path,
            "min_video_size_bytes": min_video_size_bytes,
            "actual_bytes": _file_size(storage, project.id, final_output_path) if final_output_path else 0,
        },
    )

    failed_names = [check.name for check in checks if not check.passed]
    return QualityReport(
        project_id=project.id,
        passed=not failed_names,
        checks=checks,
        warnings=[],
        errors=failed_names,
        created_at=utc_now(),
    )


def _read_optional(reader):
    try:
        return reader()
    except AppError:
        return None


def _read_render_manifest(storage: ProjectStorage, project_id: str) -> RenderManifest | None:
    try:
        data = storage.read_json(project_id, RENDER_MANIFEST_PATH)
        return RenderManifest.model_validate(data)
    except (AppError, ValidationError):
        return None


def _add_check(
    checks: list[QualityCheck],
    name: str,
    passed: bool,
    details: dict | None = None,
) -> None:
    checks.append(QualityCheck(name=name, passed=passed, details=details or {}))


def _crop_coordinates_legal(storyboard: Storyboard) -> bool:
    for shot in storyboard.shots:
        for rect in (shot.crop_start, shot.crop_end):
            x1, y1, x2, y2 = rect
            if any(coordinate < 0 or coordinate > 1 for coordinate in rect):
                return False
            if x2 <= x1 or y2 <= y1:
                return False
    return bool(storyboard.shots)


def _max_zoom_legal(storyboard: Storyboard, preset: RenderPreset) -> bool:
    for shot in storyboard.shots:
        for rect in (shot.crop_start, shot.crop_end):
            x1, y1, x2, y2 = rect
            width = x2 - x1
            height = y2 - y1
            if width <= 0 or height <= 0:
                return False
            if max(1 / width, 1 / height) > preset.max_zoom:
                return False
    return bool(storyboard.shots)


def _duration_matches(
    voice_duration_sec: float,
    storyboard_duration_sec: float,
    *,
    tolerance_sec: float,
    tolerance_ratio: float,
) -> bool:
    tolerance = max(tolerance_sec, storyboard_duration_sec * tolerance_ratio)
    return abs(voice_duration_sec - storyboard_duration_sec) <= tolerance


def _background_music_readable(storage: ProjectStorage, project_id: str, background_music) -> bool:
    if background_music is None:
        return True
    return storage.project_file_exists(project_id, background_music.file_path) and (
        storage.resolve_project_path(project_id, background_music.file_path).stat().st_size > 0
    )


def _overlay_box_visible(overlay: dict[str, float | str], *, width: int, height: int) -> bool:
    try:
        x = float(overlay["x"])
        y = float(overlay["y"])
        box_width = float(overlay["width"])
        box_height = float(overlay["height"])
    except (KeyError, TypeError, ValueError):
        return False
    return x >= 0 and y >= 0 and box_width > 0 and box_height > 0 and x + box_width <= width and y + box_height <= height


def _file_size(storage: ProjectStorage, project_id: str, relative_path: str) -> int:
    if not storage.project_file_exists(project_id, relative_path):
        return 0
    return storage.resolve_project_path(project_id, relative_path).stat().st_size

