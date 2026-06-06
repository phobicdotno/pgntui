from pgntui.signals.sparkline import render_analog, render_digital

RAMP = "▁▂▃▄▅▆▇█"


def test_analog_maps_low_and_high_to_ramp_ends() -> None:
    out = render_analog([0.0, 10.0])
    assert out[0] == RAMP[0]   # lowest -> first ramp glyph
    assert out[-1] == RAMP[-1]  # highest -> last ramp glyph


def test_analog_autoscales_to_window() -> None:
    out = render_analog([80.0, 82.5, 85.0, 87.5, 90.0])
    assert out[0] == RAMP[0]
    assert out[-1] == RAMP[-1]
    assert set(out) - set(RAMP) == set()  # only ramp glyphs


def test_analog_flat_window_is_mid_glyph() -> None:
    assert render_analog([5.0, 5.0, 5.0]) == "▄▄▄"


def test_analog_gaps_render_as_spaces() -> None:
    out = render_analog([0.0, None, 10.0])
    assert out == f"{RAMP[0]} {RAMP[-1]}"


def test_analog_all_gaps_is_blank() -> None:
    assert render_analog([None, None, None]) == "   "


def test_digital_steps_and_gaps() -> None:
    assert render_digital([0.0, 1.0, 1.0, 0.0, None]) == "▁██▁ "


def test_digital_threshold_at_half() -> None:
    assert render_digital([0.49, 0.5]) == "▁█"
