from pathlib import Path

from video_foundry.quality.checks import run_quality_checks
from video_foundry.renderer.manifest import build_render_manifest
from video_foundry.shared.schemas import (
    Asset,
    Script,
    ScriptSegment,
    Storyboard,
    StoryboardShot,
    SubtitleCue,
    SubtitlesManifest,
    VoiceConfig,
)
from video_foundry.shared.storage import ProjectStorage


def test_quality_checks_fail_without_render_manifest(tmp_path: Path) -> None:
    storage, project_id, config_dir = _quality_fixture(tmp_path)

    report = run_quality_checks(storage, project_id, config_dir=config_dir)

    failed = {check.name for check in report.checks if not check.passed}
    assert report.passed is False
    assert "render_manifest_exists" in failed
    assert "render_manifest_proves_visible_credit_overlay" in failed


def test_quality_checks_fail_when_manifest_lacks_credit_overlay(tmp_path: Path) -> None:
    storage, project_id, config_dir = _quality_fixture(tmp_path)
    _write_manifest(storage, project_id, credit_overlay={})
    storage.write_bytes(project_id, "exports/final_vertical_1080x1920.mp4", b"fake mp4")

    report = run_quality_checks(storage, project_id, config_dir=config_dir)

    failed = {check.name for check in report.checks if not check.passed}
    assert report.passed is False
    assert "render_manifest_proves_visible_credit_overlay" in failed
    assert "render_manifest_exists" not in failed


def _quality_fixture(tmp_path: Path) -> tuple[ProjectStorage, str, Path]:
    storage = ProjectStorage(tmp_path / "projects")
    project = storage.create_project(name="Quality", target_duration_sec=4)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "render-presets.json").write_text(
        '{"vertical_1080x1920":{"width":1080,"height":1920,"fps":30,"max_zoom":1.2,"safe_area":{"top":120,"right":80,"bottom":180,"left":80}}}',
        encoding="utf-8",
    )

    storage.write_bytes(project.id, "assets/original.png", b"image-bytes")
    storage.write_json(
        project.id,
        "metadata/asset.json",
        Asset(
            project_id=project.id,
            title="Source title",
            source_url="https://example.test/source",
            image_original_path="assets/original.png",
            description="Source description",
            credit="Example Observatory",
            sha256="a" * 64,
        ),
    )
    storage.write_json(
        project.id,
        "script/script.json",
        Script(
            project_id=project.id,
            duration_target_sec=4,
            narration="Narration.",
            segments=[ScriptSegment(start_sec=0, end_sec=4, text="Narration.")],
            review_notes="Grounded in source.",
            approved=True,
        ),
    )
    storage.write_json(
        project.id,
        "storyboard/storyboard.json",
        Storyboard(
            project_id=project.id,
            duration_sec=4,
            approved=True,
            shots=[
                StoryboardShot(
                    id="shot_001",
                    start_sec=0,
                    end_sec=4,
                    type="push_in",
                    crop_start=(0, 0, 1, 1),
                    crop_end=(0.02, 0.02, 0.98, 0.98),
                )
            ],
        ),
    )
    storage.write_bytes(project.id, "audio/narration.wav", b"wav")
    storage.write_json(
        project.id,
        "audio/voice.json",
        VoiceConfig(
            project_id=project.id,
            audio_path="audio/narration.wav",
            duration_sec=4,
            audio_format="wav",
        ),
    )
    storage.write_bytes(project.id, "subtitles/subtitles.srt", b"1\n00:00:00,000 --> 00:00:04,000\nNarration.\n")
    storage.write_bytes(project.id, "subtitles/subtitles.vtt", b"WEBVTT\n\n00:00:00.000 --> 00:00:04.000\nNarration.\n")
    storage.write_json(
        project.id,
        "subtitles/subtitles.json",
        SubtitlesManifest(
            project_id=project.id,
            storyboard_version=1,
            cues=[SubtitleCue(index=1, start_sec=0, end_sec=4, text="Narration.")],
        ),
    )
    return storage, project.id, config_dir


def _write_manifest(storage: ProjectStorage, project_id: str, *, credit_overlay: dict) -> None:
    manifest = build_render_manifest(
        project_id=project_id,
        format_name="vertical_1080x1920",
        fps=30,
        width=1080,
        height=1920,
        duration_sec=4,
        source_image_path="assets/original.png",
        source_image_sha256="a" * 64,
        storyboard_version=1,
        subtitles_path="subtitles/subtitles.srt",
        credit_text="Example Observatory",
        subtitle_overlay={"x": 80, "y": 1600, "width": 920, "height": 120, "units": "px"},
        credit_overlay=credit_overlay,
        preview_output_path=None,
        final_output_path="exports/final_vertical_1080x1920.mp4",
        frame_count=120,
        keyframes=[],
    )
    storage.write_json(project_id, "renders/render-manifest.json", manifest)
