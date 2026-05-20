from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from video_foundry.shared.paths import validate_identifier_value, validate_relative_project_path_value
from video_foundry.shared.schemas import VoiceConfig


class VoiceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audio_path: str
    duration_sec: float = Field(ge=0)
    format: str = Field(min_length=1, max_length=16)
    provider: str = Field(min_length=1, max_length=80)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("audio_path")
    @classmethod
    def validate_audio_path(cls, value: str) -> str:
        return validate_relative_project_path_value(value)

    @field_validator("format", "provider")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return validate_identifier_value(value)


class VoiceProviderInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    enabled: bool = True
    default: bool = False

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_identifier_value(value, "provider")


class VoicePreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    name: str
    language: str = Field(min_length=2, max_length=32)
    style: str | None = Field(default=None, max_length=80)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_identifier_value(value, "voice_id")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        return validate_identifier_value(value, "provider")


class TTSProvider(Protocol):
    provider_name: str

    def synthesize(
        self,
        text: str,
        voice_config: VoiceConfig,
        *,
        output_path: Path,
        relative_audio_path: str,
    ) -> VoiceResult:
        """Synthesize narration audio into output_path and return safe metadata."""

