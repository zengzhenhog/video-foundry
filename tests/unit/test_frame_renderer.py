from pathlib import Path

from PIL import Image

from video_foundry.renderer.frame_renderer import RenderPresetSize, render_storyboard_frames
from video_foundry.shared.schemas import Storyboard, StoryboardShot, SubtitleCue


def test_frame_renderer_writes_preset_sized_frames(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    Image.new("RGB", (120, 80), color=(20, 80, 120)).save(image_path)
    storyboard = Storyboard(
        project_id="project_1",
        format="square_1080x1080",
        fps=2,
        duration_sec=1,
        safe_area={"top": 0.1, "right": 0.1, "bottom": 0.1, "left": 0.1},
        shots=[
            StoryboardShot(
                id="shot_001",
                start_sec=0,
                end_sec=1,
                type="push_in",
                crop_start=(0, 0, 1, 1),
                crop_end=(0.1, 0.1, 0.9, 0.9),
                caption="Caption",
            )
        ],
    )

    result = render_storyboard_frames(
        project_id="project_1",
        image_path=image_path,
        frames_dir=tmp_path / "frames",
        relative_frames_dir="renders/frames",
        storyboard=storyboard,
        output_size=RenderPresetSize(width=64, height=48),
        cues=[SubtitleCue(index=1, start_sec=0, end_sec=1, text="Caption")],
        credit_text="Example Observatory",
    )

    assert len(result.frame_paths) == 2
    with Image.open(result.frame_paths[0]) as frame:
        assert frame.size == (64, 48)
    assert result.credit_overlay["units"] == "px"
    assert result.keyframes[0].output_path == "renders/frames/frame_000000.png"

