from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from video_foundry.ai.script_generator import ensure_script_approved
from video_foundry.shared.errors import AppError
from video_foundry.shared.paths import PROJECT_METADATA_FILE
from video_foundry.shared.provider_runtime import provider_name_for, run_provider_call
from video_foundry.shared.schemas import Project, ProjectStatus, VoiceConfig, utc_now
from video_foundry.shared.storage import ProjectStorage
from video_foundry.voice.base import TTSProvider, VoicePreset, VoiceProviderInfo
from video_foundry.voice.mock_provider import MockTTSProvider


VOICE_CONFIG_PATH = "audio/voice.json"
NARRATION_RELATIVE_PATH = "audio/narration.wav"
STALE_ON_VOICE_CHANGE_PATHS = {
    "render": "renders/render-manifest.json",
    "export": "exports/quality-report.json",
}


def get_tts_provider(provider_name: str | None = None) -> TTSProvider:
    selected = (provider_name or os.environ.get("VIDEO_FOUNDRY_TTS_PROVIDER") or "mock").strip()
    if selected == "mock":
        return MockTTSProvider()
    raise AppError(
        code="unsupported_tts_provider",
        message="The requested TTS provider is not enabled.",
        status_code=422,
        step="voice_provider",
        retryable=False,
        suggested_correction="Use the mock provider or enable a supported provider with environment variables.",
        details={"provider": selected},
    )


def list_voice_providers() -> list[VoiceProviderInfo]:
    return [
        VoiceProviderInfo(id="mock", name="Mock TTS", enabled=True, default=True),
    ]


def load_voice_presets(config_dir: Path) -> list[VoicePreset]:
    preset_path = config_dir / "voices.example.json"
    try:
        data = json.loads(preset_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AppError(
            code="voice_presets_missing",
            message="Voice preset configuration was not found.",
            status_code=500,
            step="voice_presets",
            retryable=False,
            suggested_correction="Restore config/voices.example.json.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise AppError(
            code="voice_presets_invalid",
            message="Voice preset configuration is invalid JSON.",
            status_code=500,
            step="voice_presets",
            retryable=False,
            suggested_correction="Fix config/voices.example.json.",
        ) from exc

    voices = data.get("voices")
    if not isinstance(voices, list):
        raise AppError(
            code="voice_presets_invalid",
            message="Voice preset configuration must contain a voices array.",
            status_code=500,
            step="voice_presets",
            retryable=False,
            suggested_correction="Fix config/voices.example.json.",
        )

    try:
        return [VoicePreset.model_validate(item) for item in voices]
    except ValidationError as exc:
        raise AppError(
            code="voice_presets_invalid",
            message="Voice preset configuration contains invalid entries.",
            status_code=500,
            step="voice_presets",
            retryable=False,
            suggested_correction="Fix config/voices.example.json.",
            details={"errors": exc.errors(include_url=False, include_input=False)},
        ) from exc


def read_voice_config(storage: ProjectStorage, project_id: str) -> VoiceConfig | None:
    try:
        data = storage.read_json(project_id, VOICE_CONFIG_PATH)
    except AppError as exc:
        if exc.detail.code == "project_file_not_found":
            return None
        raise

    try:
        return VoiceConfig.model_validate(data)
    except ValidationError as exc:
        raise AppError(
            code="voice_config_invalid",
            message="Voice configuration metadata is invalid.",
            status_code=500,
            step="voice_storage",
            retryable=False,
            suggested_correction="Inspect audio/voice.json and restore a valid voice record.",
            details={"errors": exc.errors(include_url=False, include_input=False)},
        ) from exc


def save_voice_config(
    storage: ProjectStorage,
    project: Project,
    voice_config: VoiceConfig,
) -> VoiceConfig:
    get_tts_provider(voice_config.provider)
    existing = read_voice_config(storage, project.id)
    content_changed = existing is None or _voice_settings_changed(existing, voice_config)
    now = utc_now()
    updates = {
        "project_id": project.id,
        "updated_at": now,
    }
    if existing and not content_changed:
        updates.update(
            {
                "audio_path": existing.audio_path,
                "duration_sec": existing.duration_sec,
                "audio_format": existing.audio_format,
                "provider_metadata": existing.provider_metadata,
            }
        )
    else:
        updates.update(
            {
                "audio_path": None,
                "duration_sec": None,
                "audio_format": None,
                "provider_metadata": {},
            }
        )

    next_config = voice_config.model_copy(update=updates, deep=True)
    storage.write_json(project.id, VOICE_CONFIG_PATH, next_config)
    if content_changed:
        _refresh_project_after_voice_change(
            storage,
            project,
            stale_voice=bool(existing and existing.audio_path),
            rollback_to_script=bool(existing and existing.audio_path),
        )
    return next_config


def generate_narration(storage: ProjectStorage, project_id: str) -> VoiceConfig:
    project = storage.read_project(project_id)
    script = ensure_script_approved(storage, project.id, step="voice_generation")
    voice_config = read_voice_config(storage, project.id)
    if voice_config is None:
        raise AppError(
            code="voice_config_not_found",
            message="Voice configuration has not been saved.",
            status_code=409,
            step="voice_generation",
            retryable=True,
            suggested_correction="Save voice settings before generating narration.",
        )

    provider = get_tts_provider(voice_config.provider)
    output_path = storage.resolve_project_path(project.id, NARRATION_RELATIVE_PATH)
    result = run_provider_call(
        lambda: provider.synthesize(
            script.narration,
            voice_config,
            output_path=output_path,
            relative_audio_path=NARRATION_RELATIVE_PATH,
        ),
        provider_name=provider_name_for(provider),
        operation="voice_generation",
        step="voice_generation",
    )
    next_config = voice_config.model_copy(
        update={
            "project_id": project.id,
            "audio_path": result.audio_path,
            "duration_sec": result.duration_sec,
            "audio_format": result.format,
            "provider_metadata": {
                "provider": result.provider,
                **result.provider_metadata,
            },
            "updated_at": utc_now(),
        },
        deep=True,
    )
    storage.write_json(project.id, VOICE_CONFIG_PATH, next_config)
    _mark_project_voice_ready(storage, project)
    return next_config


def _voice_settings_changed(existing: VoiceConfig, next_config: VoiceConfig) -> bool:
    fields = ("provider", "voice_id", "language", "speed", "volume_gain_db", "style", "settings")
    return any(getattr(existing, field) != getattr(next_config, field) for field in fields)


def _refresh_project_after_voice_change(
    storage: ProjectStorage,
    project: Project,
    *,
    stale_voice: bool,
    rollback_to_script: bool,
) -> None:
    next_project = project.model_copy(deep=True)
    next_project.updated_at = utc_now()
    if rollback_to_script and project.status in {
        ProjectStatus.VOICE_READY,
        ProjectStatus.RENDERED,
        ProjectStatus.EXPORTED,
    }:
        next_project.status = ProjectStatus.SCRIPT_APPROVED
        next_project.current_step = "voice_config"

    stale_artifacts = dict(next_project.stale_artifacts)
    if stale_voice:
        stale_artifacts["voice"] = True
    for artifact, relative_path in STALE_ON_VOICE_CHANGE_PATHS.items():
        if storage.project_file_exists(project.id, relative_path):
            stale_artifacts[artifact] = True
    next_project.stale_artifacts = stale_artifacts
    storage.write_json(project.id, PROJECT_METADATA_FILE, next_project)


def _mark_project_voice_ready(storage: ProjectStorage, project: Project) -> None:
    next_project = project.model_copy(deep=True)
    next_project.status = ProjectStatus.VOICE_READY
    next_project.current_step = "voice_ready"
    next_project.updated_at = utc_now()
    stale_artifacts = dict(next_project.stale_artifacts)
    stale_artifacts.pop("voice", None)
    for artifact, relative_path in STALE_ON_VOICE_CHANGE_PATHS.items():
        if storage.project_file_exists(project.id, relative_path):
            stale_artifacts[artifact] = True
    next_project.stale_artifacts = stale_artifacts
    storage.write_json(project.id, PROJECT_METADATA_FILE, next_project)
