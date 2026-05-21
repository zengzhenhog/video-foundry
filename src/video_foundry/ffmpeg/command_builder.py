from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from video_foundry.audio.mixer import AudioMixPlan


@dataclass(frozen=True)
class FFmpegCommandSpec:
    command: list[str]
    output_path: Path
    uses_background_music: bool


def build_video_assembly_command(
    *,
    frames_pattern: Path,
    fps: int,
    duration_sec: float,
    output_path: Path,
    audio_mix: AudioMixPlan,
    ffmpeg_binary: str = "ffmpeg",
) -> FFmpegCommandSpec:
    command = [
        ffmpeg_binary,
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(frames_pattern),
        "-i",
        str(audio_mix.narration_path),
    ]

    if audio_mix.background_music_path:
        if audio_mix.loop_background:
            command.extend(["-stream_loop", "-1"])
        command.extend(["-i", str(audio_mix.background_music_path)])
        fade_out_start = max(0.0, duration_sec - audio_mix.fade_out_sec)
        music_filter = (
            f"[2:a]volume={_db_to_linear(audio_mix.background_volume_gain_db):.6f},"
            f"atrim=0:{duration_sec:.3f},asetpts=PTS-STARTPTS"
        )
        if audio_mix.fade_in_sec > 0:
            music_filter += f",afade=t=in:st=0:d={audio_mix.fade_in_sec:.3f}"
        if audio_mix.fade_out_sec > 0:
            music_filter += f",afade=t=out:st={fade_out_start:.3f}:d={audio_mix.fade_out_sec:.3f}"
        filter_complex = f"{music_filter}[bg];[1:a][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        command.extend(["-filter_complex", filter_complex, "-map", "0:v:0", "-map", "[aout]"])
    else:
        command.extend(["-map", "0:v:0", "-map", "1:a:0"])

    command.extend(
        [
            "-t",
            f"{duration_sec:.3f}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
    )
    return FFmpegCommandSpec(
        command=command,
        output_path=output_path,
        uses_background_music=audio_mix.has_background_music,
    )


def _db_to_linear(gain_db: float) -> float:
    return 10 ** (gain_db / 20)

