from functools import lru_cache
import os
from pathlib import Path

from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    """Minimal runtime settings for local development."""

    app_name: str = "video-foundry"
    app_version: str = "0.1.0"
    root_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])
    projects_dir: Path | None = None
    config_dir: Path | None = None

    @property
    def resolved_projects_dir(self) -> Path:
        return self.projects_dir or self.root_dir / "projects"

    @property
    def resolved_config_dir(self) -> Path:
        return self.config_dir or self.root_dir / "config"


@lru_cache
def get_settings() -> AppSettings:
    root_dir = Path(os.environ.get("VIDEO_FOUNDRY_ROOT_DIR", Path(__file__).resolve().parents[3]))
    projects_dir = os.environ.get("VIDEO_FOUNDRY_PROJECTS_DIR")
    config_dir = os.environ.get("VIDEO_FOUNDRY_CONFIG_DIR")

    return AppSettings(
        root_dir=root_dir,
        projects_dir=Path(projects_dir) if projects_dir else None,
        config_dir=Path(config_dir) if config_dir else None,
    )

