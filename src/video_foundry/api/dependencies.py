from video_foundry.shared.config import get_settings
from video_foundry.shared.storage import ProjectStorage


def get_project_storage() -> ProjectStorage:
    return ProjectStorage(get_settings().resolved_projects_dir)

