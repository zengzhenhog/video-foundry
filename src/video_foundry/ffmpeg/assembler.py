from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from video_foundry.audio.mixer import AudioMixPlan
from video_foundry.ffmpeg.command_builder import FFmpegCommandSpec, build_video_assembly_command
from video_foundry.shared.errors import AppError


def assemble_video(
    *,
    frames_dir: Path,
    fps: int,
    duration_sec: float,
    output_path: Path,
    audio_mix: AudioMixPlan,
    ffmpeg_binary: str = "ffmpeg",
) -> FFmpegCommandSpec:
    resolved_binary = shutil.which(ffmpeg_binary)
    if resolved_binary is None:
        raise AppError(
            code="ffmpeg_not_available",
            message="FFmpeg is not available on PATH.",
            status_code=503,
            step="ffmpeg_assembly",
            retryable=True,
            suggested_correction="Install FFmpeg and ensure it is available on PATH.",
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    spec = build_video_assembly_command(
        frames_pattern=frames_dir / "frame_%06d.png",
        fps=fps,
        duration_sec=duration_sec,
        output_path=output_path,
        audio_mix=audio_mix,
        ffmpeg_binary=resolved_binary,
    )
    result = subprocess.run(spec.command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AppError(
            code="ffmpeg_assembly_failed",
            message="FFmpeg failed to assemble the video.",
            status_code=500,
            step="ffmpeg_assembly",
            retryable=True,
            suggested_correction="Inspect render inputs and retry after correcting FFmpeg errors.",
            details={"stderr_tail": result.stderr[-2000:]},
        )
    return spec

