from video_foundry.renderer.manifest import build_render_manifest
from video_foundry.shared.schemas import RenderKeyframe


def test_render_manifest_records_source_hash_credit_and_output() -> None:
    manifest = build_render_manifest(
        project_id="project_1",
        format_name="vertical_1080x1920",
        fps=30,
        width=1080,
        height=1920,
        duration_sec=5,
        source_image_path="assets/original.png",
        source_image_sha256="a" * 64,
        storyboard_version=2,
        subtitles_path="subtitles/subtitles.srt",
        credit_text="Example Observatory",
        subtitle_overlay={"x": 10, "y": 20, "units": "px"},
        credit_overlay={"x": 10, "y": 20, "units": "px"},
        preview_output_path="renders/preview_vertical_1080x1920.mp4",
        final_output_path=None,
        frame_count=150,
        keyframes=[
            RenderKeyframe(
                shot_id="shot_001",
                frame_index=0,
                time_sec=0,
                crop=(0, 0, 1, 1),
                output_path="renders/frames/frame_000000.png",
            )
        ],
    )

    assert manifest.source_image_sha256 == "a" * 64
    assert manifest.credit_text == "Example Observatory"
    assert manifest.preview_output_path == "renders/preview_vertical_1080x1920.mp4"
    assert "No generative image" in manifest.deterministic_rules[1]

