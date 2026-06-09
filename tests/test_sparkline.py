from pgntui.signals.sparkline import (
    render_analog,
    render_analog_rows,
    render_digital,
    render_digital_rows,
)

RAMP = "▁▂▃▄▅▆▇█"


def test_analog_maps_low_and_high_to_ramp_ends() -> None:
    out = render_analog([0.0, 10.0])
    assert out[0] == RAMP[0]  # lowest -> first ramp glyph
    assert out[-1] == RAMP[-1]  # highest -> last ramp glyph


def test_analog_autoscales_to_window() -> None:
    out = render_analog([80.0, 82.5, 85.0, 87.5, 90.0])
    assert out[0] == RAMP[0]
    assert out[-1] == RAMP[-1]
    assert set(out) - set(RAMP) == set()  # only ramp glyphs


def test_analog_flat_window_is_mid_glyph() -> None:
    assert render_analog([5.0, 5.0, 5.0]) == "▄▄▄"


def test_analog_handles_negative_values() -> None:
    # A bipolar signal (e.g. reverse RPM) autoscales across its window: the
    # lowest value — even when negative — is the baseline, scaling up through
    # zero to the highest. The sign isn't a special case; it just scales in.
    assert render_analog([-2000.0, 0.0, 2000.0, 4000.0, 6000.0]) == "▁▃▅▆█"
    # An all-negative (full reverse) window still scales within its own range.
    out = render_analog([-500.0, -2000.0, -1000.0])
    assert out[0] == RAMP[-1]  # -500 is the highest -> top of the ramp
    assert out[1] == RAMP[0]  # -2000 is the lowest -> baseline


def test_analog_rows_handles_negative_values() -> None:
    rows = render_analog_rows([-2000.0, 0.0, 2000.0, 4000.0, 6000.0], 3)
    assert len(rows) == 3
    # Bottom row carries the lowest (most-reverse) value; bars grow up toward
    # the highest (most-forward).
    assert rows[-1][0] != " "  # the -2000 column shows a baseline glyph
    assert rows[0][-1] == "█"  # 6000 fills the full height


def test_analog_gaps_render_as_spaces() -> None:
    out = render_analog([0.0, None, 10.0])
    assert out == f"{RAMP[0]} {RAMP[-1]}"


def test_analog_all_gaps_is_blank() -> None:
    assert render_analog([None, None, None]) == "   "


def test_digital_steps_and_gaps() -> None:
    assert render_digital([0.0, 1.0, 1.0, 0.0, None]) == "▁██▁ "


def test_digital_threshold_at_half() -> None:
    assert render_digital([0.49, 0.5]) == "▁█"


# ---- multi-row renderers ---------------------------------------------------


def test_analog_rows_height_one_matches_single_row() -> None:
    cols = [0.0, 2.5, 5.0, 7.5, 10.0]
    assert render_analog_rows(cols, 1) == [render_analog(cols)]


def test_analog_rows_stacks_from_the_bottom() -> None:
    # Two rows, low + high: the high column fills both rows, the low fills only
    # the bottom 1/8; the bottom line still matches the single-row render.
    rows = render_analog_rows([0.0, 10.0], 2)
    assert len(rows) == 2
    assert rows[0] == " █"  # top: low empty, high full
    assert rows[1] == "▁█"  # bottom: low baseline, high full (matches 1-row)
    assert rows[1] == render_analog([0.0, 10.0])


def test_analog_rows_gaps_span_every_row() -> None:
    rows = render_analog_rows([None, 10.0, None], 3)
    assert [r[0] for r in rows] == [" ", " ", " "]
    assert [r[2] for r in rows] == [" ", " ", " "]


def test_digital_rows_on_fills_all_off_is_baseline() -> None:
    rows = render_digital_rows([0.0, 1.0], 3)
    assert len(rows) == 3
    assert rows == [" █", " █", "▁█"]  # ON full height; OFF only bottom baseline


def test_digital_rows_height_one_matches_single_row() -> None:
    cols = [0.0, 1.0, 1.0, 0.0, None]
    assert render_digital_rows(cols, 1) == [render_digital(cols)]
