from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from video_foundry.shared.schemas import Script


class ScriptGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    title: str = Field(default="", max_length=240)
    description: str = Field(min_length=1)
    source_url: str = Field(min_length=1, max_length=2048)
    credit: str = Field(min_length=1, max_length=500)
    target_language: str = Field(default="zh-CN", min_length=2, max_length=32)
    target_duration_sec: float = Field(gt=0, le=3600)
    user_draft: str | None = Field(default=None, max_length=20000)
    grounding_instructions: str = Field(
        default=(
            "Use only the official source description, source URL, credit, and optional "
            "user draft. Do not introduce distances, dates, object types, causal claims, "
            "or observation details that are not present in those inputs."
        ),
        min_length=1,
    )


class LLMProvider(Protocol):
    def generate_script(self, script_input: ScriptGenerationInput) -> Script:
        """Generate a structured narration script from grounded source inputs."""
