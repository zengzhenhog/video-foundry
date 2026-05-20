from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from video_foundry.api.dependencies import get_project_storage
from video_foundry.shared.config import get_settings
from video_foundry.shared.errors import AppError
from video_foundry.shared.schemas import VoiceConfig
from video_foundry.shared.storage import ProjectStorage
from video_foundry.voice.provider_registry import (
    generate_narration,
    list_voice_providers,
    load_voice_presets,
    read_voice_config,
    save_voice_config,
)
from video_foundry.voice.base import VoicePreset, VoiceProviderInfo


project_router = APIRouter(prefix="/api/projects/{project_id}/voice", tags=["voice"])
global_router = APIRouter(prefix="/api/voice", tags=["voice"])


class VoiceConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(default="mock", min_length=1, max_length=80)
    voice_id: str = Field(min_length=1, max_length=120)
    language: str = Field(default="zh-CN", min_length=2, max_length=32)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    volume_gain_db: float = Field(default=0.0, ge=-24.0, le=12.0)
    style: str | None = Field(default=None, max_length=80)


class VoiceProvidersResponse(BaseModel):
    providers: list[VoiceProviderInfo]


class VoicePresetsResponse(BaseModel):
    presets: list[VoicePreset]


@global_router.get("/providers", response_model=VoiceProvidersResponse)
def get_voice_providers() -> VoiceProvidersResponse:
    return VoiceProvidersResponse(providers=list_voice_providers())


@global_router.get("/presets", response_model=VoicePresetsResponse)
def get_voice_presets() -> VoicePresetsResponse:
    return VoicePresetsResponse(presets=load_voice_presets(get_settings().resolved_config_dir))


@project_router.put("/config", response_model=VoiceConfig)
def put_voice_config(
    project_id: str,
    request: VoiceConfigRequest,
    storage: ProjectStorage = Depends(get_project_storage),
) -> VoiceConfig:
    project = storage.read_project(project_id)
    return save_voice_config(
        storage,
        project,
        VoiceConfig(
            project_id=project.id,
            provider=request.provider,
            voice_id=request.voice_id,
            language=request.language,
            speed=request.speed,
            volume_gain_db=request.volume_gain_db,
            style=request.style,
        ),
    )


@project_router.post("/generate", response_model=VoiceConfig)
def post_voice_generate(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> VoiceConfig:
    return generate_narration(storage, project_id)


@project_router.get("/audio")
def get_voice_audio(
    project_id: str,
    storage: ProjectStorage = Depends(get_project_storage),
) -> FileResponse:
    storage.read_project(project_id)
    voice_config = read_voice_config(storage, project_id)
    if voice_config is None or voice_config.audio_path is None:
        raise AppError(
            code="voice_audio_not_found",
            message="Narration audio has not been generated.",
            status_code=404,
            step="voice_audio",
            retryable=True,
            suggested_correction="Generate narration audio first.",
        )

    audio_path = storage.resolve_project_path(project_id, voice_config.audio_path)
    if not audio_path.exists():
        raise AppError(
            code="voice_audio_not_found",
            message="Narration audio file was not found.",
            status_code=404,
            step="voice_audio",
            retryable=True,
            suggested_correction="Regenerate narration audio.",
        )

    audio_format = voice_config.audio_format or audio_path.suffix.lstrip(".").lower()
    media_type = "audio/wav" if audio_format == "wav" else "application/octet-stream"
    return FileResponse(audio_path, media_type=media_type, filename=audio_path.name)

