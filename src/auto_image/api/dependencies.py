from auto_image.shared.config import get_settings
from auto_image.shared.storage import ProjectStorage


def get_project_storage() -> ProjectStorage:
    return ProjectStorage(get_settings().resolved_projects_dir)
