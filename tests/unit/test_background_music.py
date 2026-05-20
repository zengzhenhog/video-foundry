from pathlib import Path

from video_foundry.audio.background_music import save_background_music
from video_foundry.shared.storage import ProjectStorage


def test_background_music_upload_writes_file_and_metadata(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "projects")
    project = storage.create_project(name="Music project")

    music = save_background_music(
        storage,
        project,
        original_filename="bed.mp3",
        content=b"ID3 test music bytes",
    )

    assert music.file_path == "audio/background_music.mp3"
    assert music.original_filename == "bed.mp3"
    assert music.project_id == project.id
    assert (storage.projects_root / project.id / "audio" / "background_music.mp3").exists()
    assert (storage.projects_root / project.id / "audio" / "background_music.json").exists()

