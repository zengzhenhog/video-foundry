import pytest
from pydantic import ValidationError

from auto_image.shared.schemas import (
    Asset,
    BackgroundMusic,
    Project,
    ProjectStatus,
    QualityReport,
    RenderJob,
    Script,
    ScriptSegment,
    Storyboard,
    StoryboardShot,
    VoiceConfig,
)


def test_project_status_enum_contains_pipeline_states() -> None:
    assert [status.value for status in ProjectStatus] == [
        "draft",
        "asset_ready",
        "script_ready",
        "script_approved",
        "storyboard_ready",
        "storyboard_approved",
        "voice_ready",
        "rendered",
        "exported",
        "failed",
    ]


def test_project_schema_version_and_identifier_validation() -> None:
    project = Project(id="project_1", name="Demo")

    assert project.schema_version == "1.0"
    assert project.status is ProjectStatus.DRAFT

    with pytest.raises(ValidationError):
        Project(id="../project", name="Bad")


def test_project_duration_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Project(id="project_1", name="Demo", target_duration_sec=-1)


def test_disk_models_use_relative_paths() -> None:
    asset = Asset(
        project_id="project_1",
        image_original_path="assets/original.jpg",
        image_preview_path="assets/preview.jpg",
    )

    assert asset.image_original_path == "assets/original.jpg"

    with pytest.raises(ValidationError):
        Asset(project_id="project_1", image_original_path="../outside.jpg")


def test_script_segment_time_order_is_validated() -> None:
    segment = ScriptSegment(start_sec=0, end_sec=1.5, text="Hello")

    assert segment.end_sec == 1.5

    with pytest.raises(ValidationError):
        ScriptSegment(start_sec=2, end_sec=1, text="Backwards")


def test_script_requires_non_negative_timing_and_project_id() -> None:
    script = Script(project_id="project_1", duration_target_sec=30)

    assert script.schema_version == "1.0"

    with pytest.raises(ValidationError):
        Script(project_id="project/1", duration_target_sec=30)


def test_voice_config_bounds_and_relative_audio_path() -> None:
    voice = VoiceConfig(speed=1.2, volume_gain_db=-3, audio_path="audio/narration.wav")

    assert voice.audio_path == "audio/narration.wav"

    with pytest.raises(ValidationError):
        VoiceConfig(speed=0.25)

    with pytest.raises(ValidationError):
        VoiceConfig(audio_path="C:/secret/narration.wav")


def test_background_music_timing_and_path_validation() -> None:
    music = BackgroundMusic(file_path="audio/background_music.mp3", original_filename="song.mp3")

    assert music.loop is True

    with pytest.raises(ValidationError):
        BackgroundMusic(file_path="audio/background_music.mp3", original_filename="song.mp3", fade_in_sec=-1)


def test_storyboard_shot_crop_coordinates_are_unit_interval() -> None:
    shot = StoryboardShot(
        id="shot_1",
        start_sec=0,
        end_sec=5,
        type="pan",
        crop_start=(0, 0, 1, 1),
        crop_end=(0.1, 0.1, 0.9, 0.9),
    )

    assert shot.crop_start == (0, 0, 1, 1)

    with pytest.raises(ValidationError):
        StoryboardShot(
            id="shot_2",
            start_sec=0,
            end_sec=5,
            type="pan",
            crop_start=(0, 0, 1.1, 1),
            crop_end=(0, 0, 1, 1),
        )


def test_storyboard_safe_area_and_format_validation() -> None:
    storyboard = Storyboard(project_id="project_1", duration_sec=10)

    assert storyboard.schema_version == "1.0"

    with pytest.raises(ValidationError):
        Storyboard(project_id="project_1", duration_sec=10, safe_area={"top": 1.2})

    with pytest.raises(ValidationError):
        Storyboard(project_id="project_1", duration_sec=10, format="../format")


def test_render_job_validates_id_progress_and_output_paths() -> None:
    job = RenderJob(id="job_1", project_id="project_1", type="render", output_paths=["renders/out.mp4"])

    assert job.progress == 0

    with pytest.raises(ValidationError):
        RenderJob(id="../job", project_id="project_1", type="render")

    with pytest.raises(ValidationError):
        RenderJob(id="job_1", project_id="project_1", type="render", progress=2)


def test_quality_report_is_disk_schema_and_project_scoped() -> None:
    report = QualityReport(project_id="project_1", passed=True)

    assert report.schema_version == "1.0"

    with pytest.raises(ValidationError):
        QualityReport(project_id="../project", passed=False)
