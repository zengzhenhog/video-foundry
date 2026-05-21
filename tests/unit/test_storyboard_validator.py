import pytest

from video_foundry.shared.errors import AppError
from video_foundry.shared.schemas import Storyboard, StoryboardShot
from video_foundry.storyboard.validator import validate_storyboard


def test_validator_rejects_crop_coordinates_outside_unit_interval() -> None:
    shot = StoryboardShot.model_construct(
        id="shot_001",
        start_sec=0,
        end_sec=5,
        type="pan",
        crop_start=(-0.1, 0, 1, 1),
        crop_end=(0, 0, 1, 1),
        easing="linear",
        caption="Bad crop",
    )
    storyboard = Storyboard.model_construct(
        schema_version="1.0",
        project_id="project_1",
        version=1,
        format="vertical_1080x1920",
        fps=30,
        duration_sec=5,
        safe_area={},
        shots=[shot],
        approved=False,
    )

    with pytest.raises(AppError) as exc_info:
        validate_storyboard(storyboard, max_zoom=1.12)

    assert exc_info.value.detail.code == "storyboard_crop_invalid"


def test_validator_rejects_zoom_above_render_preset_limit() -> None:
    storyboard = Storyboard(
        project_id="project_1",
        duration_sec=5,
        shots=[
            StoryboardShot(
                id="shot_001",
                start_sec=0,
                end_sec=5,
                type="push_in",
                crop_start=(0.1, 0.1, 0.9, 0.9),
                crop_end=(0.1, 0.1, 0.9, 0.9),
            )
        ],
    )

    with pytest.raises(AppError) as exc_info:
        validate_storyboard(storyboard, max_zoom=1.12)

    assert exc_info.value.detail.code == "storyboard_zoom_exceeded"


def test_validator_rejects_timeline_gaps() -> None:
    storyboard = Storyboard(
        project_id="project_1",
        duration_sec=12,
        shots=[
            StoryboardShot(
                id="shot_001",
                start_sec=0,
                end_sec=5,
                type="push_in",
                crop_start=(0, 0, 1, 1),
                crop_end=(0, 0, 1, 1),
            ),
            StoryboardShot(
                id="shot_002",
                start_sec=6,
                end_sec=12,
                type="push_in",
                crop_start=(0, 0, 1, 1),
                crop_end=(0, 0, 1, 1),
            ),
        ],
    )

    with pytest.raises(AppError) as exc_info:
        validate_storyboard(storyboard, max_zoom=1.12)

    assert exc_info.value.detail.code == "storyboard_timeline_invalid"

