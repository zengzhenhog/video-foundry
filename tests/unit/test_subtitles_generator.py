from video_foundry.shared.schemas import SubtitleCue
from video_foundry.subtitles.generator import render_srt, render_vtt


def test_srt_and_vtt_outputs_are_generated() -> None:
    cues = [
        SubtitleCue(index=1, start_sec=0, end_sec=1.25, text="First line"),
        SubtitleCue(index=2, start_sec=1.25, end_sec=3.5, text="Second line"),
    ]

    srt = render_srt(cues)
    vtt = render_vtt(cues)

    assert "00:00:00,000 --> 00:00:01,250" in srt
    assert "First line" in srt
    assert vtt.startswith("WEBVTT")
    assert "00:00:01.250 --> 00:00:03.500" in vtt

