from video_foundry.renderer.crops import easing_value, interpolate_crop


def test_crop_interpolation_uses_eased_progress() -> None:
    crop = interpolate_crop((0, 0, 1, 1), (0.2, 0.2, 0.8, 0.8), 0.5, "linear")

    assert crop == (0.1, 0.1, 0.9, 0.9)


def test_ease_in_out_is_clamped() -> None:
    assert easing_value(-1, "ease_in_out") == 0
    assert easing_value(2, "ease_in_out") == 1
    assert easing_value(0.5, "ease_in_out") == 0.5

