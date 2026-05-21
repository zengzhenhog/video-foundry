from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from video_foundry.api.dependencies import get_project_storage
from video_foundry.renderer.service import FINAL_OUTPUT_TEMPLATE, PREVIEW_OUTPUT_TEMPLATE
from video_foundry.shared.errors import AppError
from video_foundry.shared.paths import PROJECT_METADATA_FILE, validate_relative_project_path_value
from video_foundry.shared.storage import ProjectStorage


router = APIRouter(prefix="/api/projects/{project_id}", tags=["downloads"])


@dataclass(frozen=True)
class DownloadCandidate:
    kind: str
    label: str
    relative_path: str
    recommended: bool = True


class DownloadFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    label: str
    path: str
    url: str
    media_type: str
    size_bytes: int = Field(ge=0)


class MissingDownload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    label: str
    path: str


class DownloadsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    files: list[DownloadFile] = Field(default_factory=list)
    missing: list[MissingDownload] = Field(default_factory=list)


@router.get("/downloads", response_model=DownloadsResponse)
def get_downloads(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> DownloadsResponse:
    project = storage.read_project(project_id)
    files: list[DownloadFile] = []
    missing: list[MissingDownload] = []

    for candidate in _download_candidates(project.formats):
        path = storage.resolve_project_path(project.id, candidate.relative_path)
        if path.exists() and path.is_file():
            files.append(
                DownloadFile(
                    kind=candidate.kind,
                    label=candidate.label,
                    path=candidate.relative_path,
                    url=_download_url(project.id, candidate.relative_path),
                    media_type=_media_type(candidate.relative_path),
                    size_bytes=path.stat().st_size,
                )
            )
        elif candidate.recommended:
            missing.append(
                MissingDownload(
                    kind=candidate.kind,
                    label=candidate.label,
                    path=candidate.relative_path,
                )
            )

    return DownloadsResponse(project_id=project.id, files=files, missing=missing)


@router.get("/downloads/file/{relative_path:path}")
def download_project_file(
    project_id: str,
    relative_path: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> FileResponse:
    storage.read_project(project_id)
    try:
        safe_relative_path = validate_relative_project_path_value(relative_path)
    except ValueError as exc:
        raise AppError(
            code="invalid_download_path",
            message="Download path is invalid.",
            status_code=422,
            step="downloads",
            retryable=False,
            suggested_correction="Use a relative path from the project downloads list.",
        ) from exc

    path = storage.resolve_project_path(project_id, safe_relative_path)
    if not path.exists() or not path.is_file():
        raise AppError(
            code="download_not_found",
            message="The requested download file was not found.",
            status_code=404,
            step="downloads",
            retryable=True,
            suggested_correction="Generate the project artifact before downloading it.",
        )

    return FileResponse(path, media_type=_media_type(safe_relative_path), filename=path.name)


def _download_candidates(formats: list[str]) -> list[DownloadCandidate]:
    candidates: list[DownloadCandidate] = []
    for format_name in formats:
        candidates.extend(
            [
                DownloadCandidate(
                    kind="video",
                    label=f"Final MP4 ({format_name})",
                    relative_path=FINAL_OUTPUT_TEMPLATE.format(format=format_name),
                ),
                DownloadCandidate(
                    kind="video",
                    label=f"Preview MP4 ({format_name})",
                    relative_path=PREVIEW_OUTPUT_TEMPLATE.format(format=format_name),
                    recommended=False,
                ),
            ]
        )

    candidates.extend(
        [
            DownloadCandidate(kind="subtitles", label="Subtitles SRT", relative_path="subtitles/subtitles.srt"),
            DownloadCandidate(kind="subtitles", label="Subtitles VTT", relative_path="subtitles/subtitles.vtt"),
            DownloadCandidate(kind="audio", label="Narration WAV", relative_path="audio/narration.wav"),
            DownloadCandidate(
                kind="audio",
                label="Background music",
                relative_path="audio/background_music.mp3",
                recommended=False,
            ),
            DownloadCandidate(kind="metadata", label="Project metadata", relative_path=PROJECT_METADATA_FILE),
            DownloadCandidate(kind="metadata", label="Asset metadata", relative_path="metadata/asset.json"),
            DownloadCandidate(kind="metadata", label="Script JSON", relative_path="script/script.json"),
            DownloadCandidate(kind="metadata", label="Storyboard JSON", relative_path="storyboard/storyboard.json"),
            DownloadCandidate(kind="metadata", label="Render manifest", relative_path="renders/render-manifest.json"),
            DownloadCandidate(kind="quality_report", label="Quality report", relative_path="exports/quality-report.json"),
        ]
    )
    return candidates


def _download_url(project_id: str, relative_path: str) -> str:
    return f"/api/projects/{quote(project_id)}/downloads/file/{quote(relative_path)}"


def _media_type(relative_path: str) -> str:
    suffix = relative_path.rsplit(".", 1)[-1].lower() if "." in relative_path else ""
    return {
        "json": "application/json",
        "md": "text/markdown; charset=utf-8",
        "mp3": "audio/mpeg",
        "mp4": "video/mp4",
        "srt": "application/x-subrip; charset=utf-8",
        "vtt": "text/vtt; charset=utf-8",
        "wav": "audio/wav",
    }.get(suffix, "application/octet-stream")
