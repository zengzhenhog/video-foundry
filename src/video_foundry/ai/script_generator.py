from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from video_foundry.ai.base import LLMProvider, ScriptGenerationInput
from video_foundry.ai.mock_provider import MockScriptProvider
from video_foundry.shared.errors import AppError
from video_foundry.shared.paths import PROJECT_METADATA_FILE
from video_foundry.shared.schemas import Asset, Project, ProjectStatus, Script, utc_now
from video_foundry.shared.storage import ProjectStorage
from video_foundry.sources.upload_importer import (
    DOWNSTREAM_ARTIFACT_PATHS,
    read_asset_metadata,
    summarize_asset_status,
)


SCRIPT_JSON_PATH = "script/script.json"
SCRIPT_MARKDOWN_PATH = "script/script.md"
SCRIPT_DOWNSTREAM_ARTIFACTS = ("storyboard", "voice", "subtitles", "render", "export")


def generate_project_script(
    storage: ProjectStorage,
    project_id: str,
    *,
    provider: LLMProvider | None = None,
    user_draft: str | None = None,
) -> Script:
    project = storage.read_project(project_id)
    asset = _asset_ready_or_error(storage, project)
    script_input = ScriptGenerationInput(
        project_id=project.id,
        title=asset.title,
        description=asset.description,
        source_url=asset.source_url or "",
        credit=asset.credit,
        target_language=project.target_language,
        target_duration_sec=project.target_duration_sec,
        user_draft=user_draft.strip() if user_draft and user_draft.strip() else None,
    )
    output = (provider or MockScriptProvider()).generate_script(script_input)
    script = validate_provider_script_output(output, script_input)
    return _persist_script(storage, project, script, downstream_changed=True)


def read_project_script(storage: ProjectStorage, project_id: str) -> Script:
    storage.read_project(project_id)
    try:
        data = storage.read_json(project_id, SCRIPT_JSON_PATH)
    except AppError as exc:
        if exc.detail.code == "project_file_not_found":
            raise AppError(
                code="script_not_found",
                message="Script has not been generated or saved.",
                status_code=404,
                step="script_storage",
                retryable=True,
                suggested_correction="Generate or save a script first.",
            ) from exc
        raise

    try:
        return Script.model_validate(data)
    except ValidationError as exc:
        raise AppError(
            code="script_metadata_invalid",
            message="Script metadata is invalid.",
            status_code=500,
            step="script_storage",
            retryable=False,
            suggested_correction="Inspect script/script.json and restore a valid script record.",
            details={"errors": exc.errors(include_url=False, include_input=False)},
        ) from exc


def save_project_script(storage: ProjectStorage, project_id: str, script: Script) -> Script:
    project = storage.read_project(project_id)
    existing = _read_project_script_optional(storage, project.id)
    content_changed = existing is None or _script_content_changed(existing, script)
    preserve_approval = bool(existing and existing.approved and not content_changed)
    next_script = script.model_copy(
        update={
            "project_id": project.id,
            "approved": preserve_approval,
            "approved_at": existing.approved_at if preserve_approval and existing else None,
            "updated_at": utc_now(),
        },
        deep=True,
    )
    _validate_human_script(next_script)
    if preserve_approval:
        storage.write_json(project.id, SCRIPT_JSON_PATH, next_script)
        storage.write_bytes(project.id, SCRIPT_MARKDOWN_PATH, _render_script_markdown(next_script).encode("utf-8"))
        _write_project_status(storage, project, status=ProjectStatus.SCRIPT_APPROVED, current_step="script_approved")
        return next_script
    return _persist_script(storage, project, next_script, downstream_changed=existing is not None and content_changed)


def approve_script(storage: ProjectStorage, project_id: str) -> Script:
    project = storage.read_project(project_id)
    script = read_project_script(storage, project.id)
    _validate_human_script(script)

    now = utc_now()
    approved = script.model_copy(update={"approved": True, "approved_at": now, "updated_at": now}, deep=True)
    storage.write_json(project.id, SCRIPT_JSON_PATH, approved)
    storage.write_bytes(project.id, SCRIPT_MARKDOWN_PATH, _render_script_markdown(approved).encode("utf-8"))
    _write_project_status(storage, project, status=ProjectStatus.SCRIPT_APPROVED, current_step="script_approved")
    return approved


def ensure_script_approved(storage: ProjectStorage, project_id: str, *, step: str = "script_gate") -> Script:
    script = read_project_script(storage, project_id)
    if not script.approved:
        raise AppError(
            code="script_not_approved",
            message="Script must be approved before continuing.",
            status_code=409,
            step=step,
            retryable=True,
            suggested_correction="Review and approve the script first.",
        )
    return script


def validate_provider_script_output(output: Script | dict[str, Any], script_input: ScriptGenerationInput) -> Script:
    try:
        script = output if isinstance(output, Script) else Script.model_validate(output)
    except ValidationError as exc:
        raise AppError(
            code="script_provider_output_invalid",
            message="Script provider returned invalid structured output.",
            status_code=502,
            step="script_generation",
            retryable=True,
            suggested_correction="Retry generation or switch to a provider that returns the expected schema.",
            details={"errors": exc.errors(include_url=False, include_input=False)},
        ) from exc

    if script.project_id != script_input.project_id:
        raise AppError(
            code="script_provider_output_invalid",
            message="Script provider returned output for a different project.",
            status_code=502,
            step="script_generation",
            retryable=True,
            suggested_correction="Retry script generation.",
        )
    if not script.review_notes.strip():
        raise AppError(
            code="script_grounding_missing",
            message="Script provider output is missing source grounding review notes.",
            status_code=502,
            step="script_generation",
            retryable=True,
            suggested_correction="Retry generation with source grounding notes enabled.",
        )
    if not script.narration.strip() or not script.segments:
        raise AppError(
            code="script_provider_output_invalid",
            message="Script provider output must include narration and at least one segment.",
            status_code=502,
            step="script_generation",
            retryable=True,
            suggested_correction="Retry generation or edit the script manually.",
        )

    return script.model_copy(
        update={
            "language": script_input.target_language,
            "duration_target_sec": script_input.target_duration_sec,
            "approved": False,
            "approved_at": None,
            "updated_at": utc_now(),
        },
        deep=True,
    )


def _asset_ready_or_error(storage: ProjectStorage, project: Project) -> Asset:
    asset = read_asset_metadata(storage, project.id)
    status = summarize_asset_status(storage, project.id, asset=asset)
    if asset is None or not status.ready_for_script:
        missing: list[str] = []
        if not status.has_original_image:
            missing.append("image")
        if not status.has_preview_image:
            missing.append("preview")
        if not status.has_description:
            missing.append("description")
        if not status.has_source_url:
            missing.append("source_url")
        if not status.has_credit:
            missing.append("credit")
        raise AppError(
            code="asset_not_ready_for_script",
            message="Project assets are not ready for script generation.",
            status_code=409,
            step="script_generation",
            retryable=True,
            suggested_correction="Upload an image and save description, source URL, and credit first.",
            details={"missing": missing},
        )
    return asset


def _validate_human_script(script: Script) -> None:
    if not script.narration.strip():
        raise AppError(
            code="script_narration_required",
            message="Script narration cannot be empty.",
            status_code=422,
            step="script_review",
            retryable=True,
            suggested_correction="Add narration text before saving or approving.",
        )
    if not script.segments:
        raise AppError(
            code="script_segments_required",
            message="Script must contain at least one narration segment.",
            status_code=422,
            step="script_review",
            retryable=True,
            suggested_correction="Add at least one segment before saving or approving.",
        )
    if not script.review_notes.strip():
        raise AppError(
            code="script_grounding_missing",
            message="Script review notes must explain source grounding.",
            status_code=422,
            step="script_review",
            retryable=True,
            suggested_correction="Add review notes describing which source facts were used.",
        )


def _persist_script(
    storage: ProjectStorage,
    project: Project,
    script: Script,
    *,
    downstream_changed: bool,
) -> Script:
    next_script = script.model_copy(update={"approved": False, "approved_at": None, "updated_at": utc_now()}, deep=True)
    storage.write_json(project.id, SCRIPT_JSON_PATH, next_script)
    storage.write_bytes(project.id, SCRIPT_MARKDOWN_PATH, _render_script_markdown(next_script).encode("utf-8"))
    _write_project_status(
        storage,
        project,
        status=ProjectStatus.SCRIPT_READY,
        current_step="script_review",
        mark_downstream_stale=downstream_changed,
    )
    return next_script


def _write_project_status(
    storage: ProjectStorage,
    project: Project,
    *,
    status: ProjectStatus,
    current_step: str,
    mark_downstream_stale: bool = False,
) -> Project:
    next_project = project.model_copy(deep=True)
    next_project.status = status
    next_project.current_step = current_step
    next_project.updated_at = utc_now()
    if mark_downstream_stale:
        stale_artifacts = dict(next_project.stale_artifacts)
        for artifact in SCRIPT_DOWNSTREAM_ARTIFACTS:
            relative_path = DOWNSTREAM_ARTIFACT_PATHS[artifact]
            if storage.project_file_exists(project.id, relative_path):
                stale_artifacts[artifact] = True
        next_project.stale_artifacts = stale_artifacts
    storage.write_json(project.id, PROJECT_METADATA_FILE, next_project)
    return next_project


def _read_project_script_optional(storage: ProjectStorage, project_id: str) -> Script | None:
    try:
        return read_project_script(storage, project_id)
    except AppError as exc:
        if exc.detail.code == "script_not_found":
            return None
        raise


def _script_content_changed(existing: Script, next_script: Script) -> bool:
    return (
        existing.title != next_script.title
        or existing.language != next_script.language
        or existing.duration_target_sec != next_script.duration_target_sec
        or existing.narration != next_script.narration
        or existing.segments != next_script.segments
        or existing.review_notes != next_script.review_notes
    )


def _render_script_markdown(script: Script) -> str:
    lines = [
        f"# {script.title or 'Script'}",
        "",
        f"- Project: `{script.project_id}`",
        f"- Language: `{script.language}`",
        f"- Target duration: `{script.duration_target_sec:g}s`",
        f"- Approved: `{str(script.approved).lower()}`",
        "",
        "## Review Notes",
        "",
        script.review_notes.strip(),
        "",
        "## Narration",
        "",
        script.narration.strip(),
        "",
        "## Segments",
        "",
    ]
    for index, segment in enumerate(script.segments, start=1):
        lines.extend(
            [
                f"### Segment {index}",
                "",
                f"- Time: `{segment.start_sec:g}s` to `{segment.end_sec:g}s`",
                "",
                segment.text.strip(),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
