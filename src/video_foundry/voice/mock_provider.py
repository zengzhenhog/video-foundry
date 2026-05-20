from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from video_foundry.shared.schemas import VoiceConfig
from video_foundry.voice.base import VoiceResult


class MockTTSProvider:
    provider_name = "mock"

    def synthesize(
        self,
        text: str,
        voice_config: VoiceConfig,
        *,
        output_path: Path,
        relative_audio_path: str,
    ) -> VoiceResult:
        normalized = " ".join(text.split())
        duration_sec = _duration_for_text(normalized, voice_config.speed)
        sample_rate = 16_000
        samples = _tone_samples(
            duration_sec=duration_sec,
            sample_rate=sample_rate,
            frequency=_frequency_for_voice(voice_config.voice_id),
            volume_gain_db=voice_config.volume_gain_db,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(samples)

        return VoiceResult(
            audio_path=relative_audio_path,
            duration_sec=round(duration_sec, 3),
            format="wav",
            provider=self.provider_name,
            provider_metadata={
                "sample_rate_hz": sample_rate,
                "channels": 1,
                "mock": True,
            },
        )


def _duration_for_text(text: str, speed: float) -> float:
    spoken_chars = max(len(text), 1)
    return max(0.6, min(30.0, spoken_chars / (12.0 * speed)))


def _frequency_for_voice(voice_id: str) -> float:
    checksum = sum(ord(character) for character in voice_id)
    return 360.0 + float(checksum % 220)


def _tone_samples(
    *,
    duration_sec: float,
    sample_rate: int,
    frequency: float,
    volume_gain_db: float,
) -> bytes:
    frame_count = max(1, int(duration_sec * sample_rate))
    gain = min(1.0, 10 ** (volume_gain_db / 20.0))
    amplitude = int(12_000 * gain)
    fade_frames = min(frame_count // 2, int(sample_rate * 0.03))

    frames = bytearray()
    for index in range(frame_count):
        fade = 1.0
        if fade_frames:
            fade = min(1.0, index / fade_frames, (frame_count - index - 1) / fade_frames)
        sample = int(amplitude * fade * math.sin(2.0 * math.pi * frequency * index / sample_rate))
        frames.extend(struct.pack("<h", sample))
    return bytes(frames)

