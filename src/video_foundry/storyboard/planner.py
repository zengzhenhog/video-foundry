from __future__ import annotations

from pathlib import Path
from typing import Iterable

from pydantic import ValidationError

from video_foundry.ai.script_generator import ensure_script_approved
from video_foundry.shared.errors import AppError
from video_foundry.shared.paths import PROJECT_METADATA_FILE
from video_foundry.shared.schemas import Project, ProjectStatus, ScriptSegment, Storyboard, StoryboardShot, utc_now
from video_foundry.shared.storage import ProjectStorage
from video_foundry.storyboard.validator import load_render_preset, validate_storyboard
from video_foundry.voice.provider_registry import read_voice_config


STORYBOARD_JSON_PATH = "storyboard/storyboard.json"
SUBTITLES_MANIFEST_PATH = "subtitles/subtitles.json"
STALE_ON_STORYBOARD_CHANGE_PATHS = {
    "subtitles": "subtitles/subtitles.srt",
    "render": "renders/render-manifest.json",
    "export": "exports/quality-report.json",
}

_MOTION_PRESETS: tuple[tuple[str, tuple[float, float, float, float], tuple[float, float, float, float], str], ...] = (
    ("push_in", (0.0, 0.0, 1.0, 1.0), (0.02, 0.02, 0.98, 0.98), "ease_in_out"),
    ("pan_right", (0.0, 0.02, 0.96, 0.98), (0.04, 0.02, 1.0, 0.98), "ease_in_out"),
    ("pan_left", (0.04, 0.02, 1.0, 0.98), (0.0, 0.02, 0.96, 0.98), "ease_in_out"),
)


def plan_storyboard(
    *,
    project_id: str,
    segments: list[ScriptSegment],
    duration_sec: float,
    format_name: str,
    fps: int,
    safe_area: dict[str, float],
    version: int = 1,
) -> Storyboard:
    if not segments:
        raise AppError(
            code="script_segments_required",
            message="Script must contain at least one narration segment.",
            status_code=422,
            step="storyboard_planning",
            retryable=True,
            suggested_correction="Add at least one script segment before generating storyboard.",
        )
    if duration_sec <= 0:
        raise AppError(
            code="storyboard_duration_invalid",
            message="Storyboard duration must be greater than zero.",
            status_code=422,
            step="storyboard_planning",
            retryable=True,
            suggested_correction="Set a positive project, script, or narration duration.",
        )

    shots: list[StoryboardShot] = []
    shot_durations = _scaled_segment_durations(segments, duration_sec)
    start_sec = 0.0
    for index, (segment, shot_duration) in enumerate(zip(segments, shot_durations, strict=True), start=1):
        end_sec = duration_sec if index == len(segments) else round(start_sec + shot_duration, 3)
        motion_type, crop_start, crop_end, easing = _MOTION_PRESETS[(index - 1) % len(_MOTION_PRESETS)]
        shots.append(
            StoryboardShot(
                id=f"shot_{index:03d}",
                start_sec=start_sec,
                end_sec=end_sec,
                type=motion_type,
                crop_start=crop_start,
                crop_end=crop_end,
                easing=easing,
                caption=segment.text.strip(),
            )
        )
        start_sec = end_sec

    return Storyboard(
        project_id=project_id,
        version=version,
        format=format_name,
        fps=fps,
        duration_sec=duration_sec,
        safe_area=safe_area,
        shots=shots,
        approved=False,
        updated_at=utc_now(),
    )


def generate_project_storyboard(
    storage: ProjectStorage,
    project_id: str,
    *,
    config_dir: Path,
    format_name: str | None = None,
) -> Storyboard:
    project = storage.read_project(project_id)
    script = ensure_script_approved(storage, project.id, step="storyboard_generation")
    selected_format = format_name or project.formats[0]
    preset = load_render_preset(config_dir, selected_format)
    existing = read_project_storyboard_optional(storage, project.id)
    duration_sec = _storyboard_duration_sec(storage, project.id, script.duration_target_sec)
    storyboard = plan_storyboard(
        project_id=project.id,
        segments=script.segments,
        duration_sec=duration_sec,
        format_name=preset.format,
        fps=preset.fps,
        safe_area=preset.safe_area,
        version=existing.version if existing else 1,
    )
    content_changed = existing is None or _storyboard_content_changed(existing, storyboard)
    if existing and content_changed:
        storyboard = storyboard.model_copy(update={"version": existing.version + 1}, deep=True)
    validate_storyboard(storyboard, max_zoom=preset.max_zoom)
    return _persist_storyboard(
        storage,
        project,
        storyboard,
        downstream_changed=existing is not None and content_changed,
    )


def read_project_storyboard(storage: ProjectStorage, project_id: str) -> Storyboard:
    storage.read_project(project_id)
    try:
        data = storage.read_json(project_id, STORYBOARD_JSON_PATH)
    except AppError as exc:
        if exc.detail.code == "project_file_not_found":
            raise AppError(
                code="storyboard_not_found",
                message="Storyboard has not been generated or saved.",
                status_code=404,
                step="storyboard_storage",
                retryable=True,
                suggested_correction="Generate or save a storyboard first.",
            ) from exc
        raise

    try:
        return Storyboard.model_validate(data)
    except ValidationError as exc:
        raise AppError(
            code="storyboard_metadata_invalid",
            message="Storyboard metadata is invalid.",
            status_code=500,
            step="storyboard_storage",
            retryable=False,
            suggested_correction="Inspect storyboard/storyboard.json and restore a valid storyboard record.",
            details={"errors": exc.errors(include_url=False, include_input=False)},
        ) from exc


def read_project_storyboard_optional(storage: ProjectStorage, project_id: str) -> Storyboard | None:
    try:
        return read_project_storyboard(storage, project_id)
    except AppError as exc:
        if exc.detail.code == "storyboard_not_found":
            return None
        raise


def save_project_storyboard(
    storage: ProjectStorage,
    project_id: str,
    storyboard: Storyboard,
    *,
    config_dir: Path,
) -> Storyboard:
    project = storage.read_project(project_id)
    existing = read_project_storyboard_optional(storage, project.id)
    preset = load_render_preset(config_dir, storyboard.format)
    candidate_storyboard = storyboard.model_copy(
        update={
            "project_id": project.id,
            "version": existing.version if existing else 1,
            "approved": False,
            "updated_at": utc_now(),
        },
        deep=True,
    )
    content_changed = existing is None or _storyboard_content_changed(existing, candidate_storyboard)
    next_storyboard = candidate_storyboard.model_copy(
        update={"version": existing.version + 1 if existing and content_changed else candidate_storyboard.version},
        deep=True,
    )
    validate_storyboard(next_storyboard, max_zoom=preset.max_zoom)
    return _persist_storyboard(
        storage,
        project,
        next_storyboard,
        downstream_changed=existing is not None and content_changed,
    )


def approve_project_storyboard(
    storage: ProjectStorage,
    project_id: str,
    *,
    config_dir: Path,
) -> Storyboard:
    project = storage.read_project(project_id)
    storyboard = read_project_storyboard(storage, project.id)
    preset = load_render_preset(config_dir, storyboard.format)
    validate_storyboard(storyboard, max_zoom=preset.max_zoom)

    approved = storyboard.model_copy(update={"approved": True, "updated_at": utc_now()}, deep=True)
    storage.write_json(project.id, STORYBOARD_JSON_PATH, approved)
    _write_project_status(
        storage,
        project,
        status=ProjectStatus.STORYBOARD_APPROVED,
        current_step="storyboard_approved",
        clear_stale_storyboard=True,
    )
    return approved


def _scaled_segment_durations(segments: Iterable[ScriptSegment], duration_sec: float) -> list[float]:
    segment_list = list(segments)
    raw_durations = [max(0.0, segment.end_sec - segment.start_sec) for segment in segment_list]
    raw_total = sum(raw_durations)
    if raw_total <= 0:
        return [duration_sec / len(segment_list)] * len(segment_list)
    return [(raw_duration / raw_total) * duration_sec for raw_duration in raw_durations]


def _storyboard_duration_sec(storage: ProjectStorage, project_id: str, fallback_duration_sec: float) -> float:
    voice_config = read_voice_config(storage, project_id)
    if voice_config and voice_config.duration_sec and voice_config.duration_sec > 0:
        return voice_config.duration_sec
    return fallback_duration_sec


def _persist_storyboard(
    storage: ProjectStorage,
    project: Project,
    storyboard: Storyboard,
    *,
    downstream_changed: bool,
) -> Storyboard:
    next_storyboard = storyboard.model_copy(update={"approved": False, "updated_at": utc_now()}, deep=True)
    storage.write_json(project.id, STORYBOARD_JSON_PATH, next_storyboard)
    _write_project_status(
        storage,
        project,
        status=ProjectStatus.STORYBOARD_READY,
        current_step="storyboard_review",
        mark_downstream_stale=downstream_changed,
    )
    return next_storyboard


def _write_project_status(
    storage: ProjectStorage,
    project: Project,
    *,
    status: ProjectStatus,
    current_step: str,
    mark_downstream_stale: bool = False,
    clear_stale_storyboard: bool = False,
) -> Project:
    next_project = project.model_copy(deep=True)
    next_project.status = status
    next_project.current_step = current_step
    next_project.updated_at = utc_now()

    stale_artifacts = dict(next_project.stale_artifacts)
    if clear_stale_storyboard:
        stale_artifacts.pop("storyboard", None)
    if mark_downstream_stale:
        for artifact, relative_path in STALE_ON_STORYBOARD_CHANGE_PATHS.items():
            if storage.project_file_exists(project.id, relative_path):
                stale_artifacts[artifact] = True
        _mark_subtitle_manifest_stale(storage, project.id)
    next_project.stale_artifacts = stale_artifacts
    storage.write_json(project.id, PROJECT_METADATA_FILE, next_project)
    return next_project


def _mark_subtitle_manifest_stale(storage: ProjectStorage, project_id: str) -> None:
    if not storage.project_file_exists(project_id, SUBTITLES_MANIFEST_PATH):
        return
    data = storage.read_json(project_id, SUBTITLES_MANIFEST_PATH)
    data["stale"] = True
    data["updated_at"] = utc_now().isoformat()
    storage.write_json(project_id, SUBTITLES_MANIFEST_PATH, data)


def _storyboard_content_changed(existing: Storyboard, next_storyboard: Storyboard) -> bool:
    return (
        existing.format != next_storyboard.format
        or existing.fps != next_storyboard.fps
        or existing.duration_sec != next_storyboard.duration_sec
        or existing.safe_area != next_storyboard.safe_area
        or existing.shots != next_storyboard.shots
    )
