from pathlib import Path

from video_foundry.audio.mixer import build_audio_mix_plan
from video_foundry.ffmpeg.command_builder import build_video_assembly_command
from video_foundry.shared.schemas import BackgroundMusic


def test_ffmpeg_command_uses_narration_only_when_background_music_missing() -> None:
    mix = build_audio_mix_plan(narration_path=Path("narration.wav"), duration_sec=5)
    spec = build_video_assembly_command(
        frames_pattern=Path("frames/frame_%06d.png"),
        fps=30,
        duration_sec=5,
        output_path=Path("preview.mp4"),
        audio_mix=mix,
    )

    command = " ".join(spec.command)
    assert "-map 1:a:0" in command
    assert "amix" not in command
    assert str(spec.output_path) == "preview.mp4"


def test_ffmpeg_command_includes_mix_parameters_for_background_music() -> None:
    music = BackgroundMusic(file_path="audio/background_music.mp3", original_filename="bed.mp3")
    mix = build_audio_mix_plan(
        narration_path=Path("narration.wav"),
        duration_sec=5,
        background_music=music,
        background_music_path=Path("background_music.mp3"),
    )
    spec = build_video_assembly_command(
        frames_pattern=Path("frames/frame_%06d.png"),
        fps=30,
        duration_sec=5,
        output_path=Path("final.mp4"),
        audio_mix=mix,
    )

    command = " ".join(spec.command)
    assert "-stream_loop -1" in command
    assert "volume=0.125893" in command
    assert "amix=inputs=2" in command
    assert spec.uses_background_music is True

