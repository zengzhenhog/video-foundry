from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from video_foundry.shared.errors import AppError
from video_foundry.shared.paths import PROJECT_METADATA_FILE
from video_foundry.shared.schemas import BackgroundMusic, Project, utc_now
from video_foundry.shared.storage import ProjectStorage


BACKGROUND_MUSIC_METADATA_PATH = "audio/background_music.json"
MAX_BACKGROUND_MUSIC_BYTES = 50 * 1024 * 1024
ALLOWED_BACKGROUND_MUSIC_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
STALE_ON_MUSIC_CHANGE_PATHS = {
    "render": "renders/render-manifest.json",
    "export": "exports/quality-report.json",
}


def read_background_music_metadata(
    storage: ProjectStorage,
    project_id: str,
) -> BackgroundMusic | None:
    try:
        data = storage.read_json(project_id, BACKGROUND_MUSIC_METADATA_PATH)
    except AppError as exc:
        if exc.detail.code == "project_file_not_found":
            return None
        raise

    try:
        return BackgroundMusic.model_validate(data)
    except ValidationError as exc:
        raise AppError(
            code="background_music_metadata_invalid",
            message="Background music metadata is invalid.",
            status_code=500,
            step="background_music_storage",
            retryable=False,
            suggested_correction="Inspect audio/background_music.json and restore a valid record.",
            details={"errors": exc.errors(include_url=False, include_input=False)},
        ) from exc


def save_background_music(
    storage: ProjectStorage,
    project: Project,
    *,
    original_filename: str,
    content: bytes,
) -> BackgroundMusic:
    if not content:
        raise AppError(
            code="empty_background_music_upload",
            message="Uploaded background music file is empty.",
            status_code=400,
            step="background_music_upload",
            retryable=True,
            suggested_correction="Choose a non-empty audio file.",
        )
    if len(content) > MAX_BACKGROUND_MUSIC_BYTES:
        raise AppError(
            code="background_music_too_large",
            message="Uploaded background music exceeds the maximum allowed size.",
            status_code=413,
            step="background_music_upload",
            retryable=True,
            suggested_correction="Upload an audio file smaller than 50 MB.",
            details={"max_bytes": MAX_BACKGROUND_MUSIC_BYTES},
        )

    safe_name = _safe_filename(original_filename)
    extension = Path(safe_name).suffix.lower()
    if extension not in ALLOWED_BACKGROUND_MUSIC_EXTENSIONS:
        raise AppError(
            code="unsupported_background_music_format",
            message="Uploaded background music format is not supported.",
            status_code=415,
            step="background_music_upload",
            retryable=True,
            suggested_correction="Upload an MP3, WAV, M4A, AAC, or OGG file.",
            details={"allowed_extensions": sorted(ALLOWED_BACKGROUND_MUSIC_EXTENSIONS)},
        )

    relative_path = f"audio/background_music{extension}"
    storage.write_bytes(project.id, relative_path, content)
    _remove_other_background_music_files(storage, project.id, keep_relative_path=relative_path)

    music = BackgroundMusic(
        project_id=project.id,
        file_path=relative_path,
        original_filename=safe_name,
        duration_sec=None,
        volume_gain_db=-18.0,
        loop=True,
        fade_in_sec=1.0,
        fade_out_sec=2.0,
        updated_at=utc_now(),
    )
    storage.write_json(project.id, BACKGROUND_MUSIC_METADATA_PATH, music)
    _refresh_project_after_music_change(storage, project)
    return music


def _remove_other_background_music_files(
    storage: ProjectStorage,
    project_id: str,
    *,
    keep_relative_path: str,
) -> None:
    audio_dir = storage.project_path(project_id) / "audio"
    keep_path = storage.resolve_project_path(project_id, keep_relative_path)
    for candidate in audio_dir.glob("background_music.*"):
        if candidate != keep_path and candidate.is_file() and candidate.suffix.lower() != ".json":
            candidate.unlink()


def _safe_filename(filename: str) -> str:
    name = Path(filename or "background_music").name.strip()
    return name or "background_music"


def _refresh_project_after_music_change(storage: ProjectStorage, project: Project) -> None:
    next_project = project.model_copy(deep=True)
    next_project.updated_at = utc_now()
    stale_artifacts = dict(next_project.stale_artifacts)
    for artifact, relative_path in STALE_ON_MUSIC_CHANGE_PATHS.items():
        if storage.project_file_exists(project.id, relative_path):
            stale_artifacts[artifact] = True
    next_project.stale_artifacts = stale_artifacts
    storage.write_json(project.id, PROJECT_METADATA_FILE, next_project)

