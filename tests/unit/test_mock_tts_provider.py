from pathlib import Path
import wave

from video_foundry.shared.schemas import VoiceConfig
from video_foundry.voice.mock_provider import MockTTSProvider


def test_mock_tts_generates_non_empty_wav(tmp_path: Path) -> None:
    output_path = tmp_path / "narration.wav"
    provider = MockTTSProvider()

    result = provider.synthesize(
        "A short narration for local testing.",
        VoiceConfig(project_id="project_1", provider="mock", voice_id="mock-narrator"),
        output_path=output_path,
        relative_audio_path="audio/narration.wav",
    )

    assert result.audio_path == "audio/narration.wav"
    assert result.duration_sec > 0
    assert output_path.stat().st_size > 44
    with wave.open(str(output_path), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16_000
        assert wav.getnframes() > 0
