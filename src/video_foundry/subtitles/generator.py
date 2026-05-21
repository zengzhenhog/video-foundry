from __future__ import annotations

from pydantic import ValidationError

from video_foundry.ai.script_generator import ensure_script_approved
from video_foundry.shared.errors import AppError
from video_foundry.shared.paths import PROJECT_METADATA_FILE
from video_foundry.shared.schemas import Project, Script, Storyboard, SubtitleCue, SubtitlesManifest, utc_now
from video_foundry.shared.storage import ProjectStorage
from video_foundry.storyboard.planner import read_project_storyboard_optional


SUBTITLES_MANIFEST_PATH = "subtitles/subtitles.json"
SUBTITLES_SRT_PATH = "subtitles/subtitles.srt"
SUBTITLES_VTT_PATH = "subtitles/subtitles.vtt"


def generate_project_subtitles(storage: ProjectStorage, project_id: str) -> SubtitlesManifest:
    project = storage.read_project(project_id)
    script = ensure_script_approved(storage, project.id, step="subtitle_generation")
    storyboard = _approved_storyboard_or_none(storage, project)
    cues = _storyboard_cues(storyboard, script) if storyboard else _script_segment_cues(script)
    if not cues:
        raise AppError(
            code="subtitle_cues_required",
            message="Subtitles require at least one cue.",
            status_code=422,
            step="subtitle_generation",
            retryable=True,
            suggested_correction="Add script segments or storyboard shot captions before generating subtitles.",
        )

    source = "storyboard" if storyboard else "script_segments"
    manifest = SubtitlesManifest(
        project_id=project.id,
        source=source,
        storyboard_version=storyboard.version if storyboard else None,
        srt_path=SUBTITLES_SRT_PATH,
        vtt_path=SUBTITLES_VTT_PATH,
        cues=cues,
        stale=False,
        updated_at=utc_now(),
    )
    storage.write_bytes(project.id, SUBTITLES_SRT_PATH, render_srt(cues).encode("utf-8"))
    storage.write_bytes(project.id, SUBTITLES_VTT_PATH, render_vtt(cues).encode("utf-8"))
    storage.write_json(project.id, SUBTITLES_MANIFEST_PATH, manifest)
    _refresh_project_after_subtitles(storage, project)
    return manifest


def read_subtitles_manifest(storage: ProjectStorage, project_id: str) -> SubtitlesManifest:
    storage.read_project(project_id)
    try:
        data = storage.read_json(project_id, SUBTITLES_MANIFEST_PATH)
    except AppError as exc:
        if exc.detail.code == "project_file_not_found":
            raise AppError(
                code="subtitles_not_found",
                message="Subtitles have not been generated.",
                status_code=404,
                step="subtitle_storage",
                retryable=True,
                suggested_correction="Generate subtitles first.",
            ) from exc
        raise

    try:
        return SubtitlesManifest.model_validate(data)
    except ValidationError as exc:
        raise AppError(
            code="subtitles_metadata_invalid",
            message="Subtitle metadata is invalid.",
            status_code=500,
            step="subtitle_storage",
            retryable=False,
            suggested_correction="Inspect subtitles/subtitles.json and regenerate subtitles.",
            details={"errors": exc.errors(include_url=False, include_input=False)},
        ) from exc


def render_srt(cues: list[SubtitleCue]) -> str:
    blocks: list[str] = []
    for cue in cues:
        blocks.append(
            "\n".join(
                [
                    str(cue.index),
                    f"{_format_timestamp(cue.start_sec, separator=',')} --> {_format_timestamp(cue.end_sec, separator=',')}",
                    _normalize_subtitle_text(cue.text),
                ]
            )
        )
    return "\n\n".join(blocks).rstrip() + "\n"


def render_vtt(cues: list[SubtitleCue]) -> str:
    blocks = ["WEBVTT"]
    for cue in cues:
        blocks.append(
            "\n".join(
                [
                    f"{_format_timestamp(cue.start_sec, separator='.')} --> {_format_timestamp(cue.end_sec, separator='.')}",
                    _normalize_subtitle_text(cue.text),
                ]
            )
        )
    return "\n\n".join(blocks).rstrip() + "\n"


def _script_segment_cues(script: Script) -> list[SubtitleCue]:
    return [
        SubtitleCue(index=index, start_sec=segment.start_sec, end_sec=segment.end_sec, text=segment.text.strip())
        for index, segment in enumerate(script.segments, start=1)
    ]


def _storyboard_cues(storyboard: Storyboard, script: Script) -> list[SubtitleCue]:
    cues: list[SubtitleCue] = []
    for index, shot in enumerate(storyboard.shots, start=1):
        fallback_text = script.segments[index - 1].text.strip() if index <= len(script.segments) else ""
        cues.append(
            SubtitleCue(
                index=index,
                start_sec=shot.start_sec,
                end_sec=shot.end_sec,
                text=shot.caption.strip() or fallback_text,
            )
        )
    return cues


def _approved_storyboard_or_none(storage: ProjectStorage, project: Project) -> Storyboard | None:
    if project.stale_artifacts.get("storyboard"):
        return None
    storyboard = read_project_storyboard_optional(storage, project.id)
    if storyboard and storyboard.approved:
        return storyboard
    return None


def _refresh_project_after_subtitles(storage: ProjectStorage, project: Project) -> None:
    next_project = project.model_copy(deep=True)
    next_project.updated_at = utc_now()
    stale_artifacts = dict(next_project.stale_artifacts)
    stale_artifacts.pop("subtitles", None)
    next_project.stale_artifacts = stale_artifacts
    storage.write_json(project.id, PROJECT_METADATA_FILE, next_project)


def _format_timestamp(seconds: float, *, separator: str) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _normalize_subtitle_text(text: str) -> str:
    return " ".join(text.split())

