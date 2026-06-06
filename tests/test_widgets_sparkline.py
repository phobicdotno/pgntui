from pgntui.signals.base import AnalogIn, DigitalIn
from pgntui.signals.widgets import AnalogInWidget, DigitalInWidget


def _sig(**kw) -> AnalogIn:
    base = dict(id="rpm", type="analog_in", title="RPM", pgn=127488,
                field="Engine Speed", unit="rpm", min=0.0, max=6000.0, smoothing=0.0)
    base.update(kw)
    return AnalogIn(**base)


def test_update_value_with_ts_feeds_history() -> None:
    w = AnalogInWidget(_sig())
    w.update_value(1000.0, ts=0.0)
    w.update_value(2000.0, ts=1.0)
    assert w.sparkline_str(2) == "▁█"


def test_update_value_without_ts_does_not_capture() -> None:
    w = AnalogInWidget(_sig())
    w.update_value(1000.0)  # legacy call path (no ts) -> no history
    assert w.sparkline_str(3) == "   "


def test_toggle_sparkline_flips_expanded() -> None:
    w = AnalogInWidget(_sig())
    assert w.expanded is False
    w.toggle_sparkline()
    assert w.expanded is True
    w.toggle_sparkline()
    assert w.expanded is False


def test_tick_advances_window_into_gaps() -> None:
    w = AnalogInWidget(_sig())
    w.update_value(3000.0, ts=0.0)
    assert w.sparkline_str(3) == "  ▄"  # newest reading sits at the right edge
    w.tick(2.0)  # 2 s later, no new data: the point scrolls left, still visible
    assert w.sparkline_str(3) == "▄  "  # shifted left with trailing gaps
    w.tick(10.0)  # long silence: the point ages out of the 3-col window entirely
    assert w.sparkline_str(3) == "   "


def test_clear_empties_history_keeps_expanded() -> None:
    w = AnalogInWidget(_sig())
    w.update_value(1000.0, ts=0.0)
    w.toggle_sparkline()
    w.clear()
    assert w.expanded is True
    assert w.sparkline_str(2) == "  "


def test_is_focusable() -> None:
    assert AnalogInWidget(_sig()).can_focus is True


def test_clear_resets_clock_so_new_data_shows_after_switch() -> None:
    # Instance switch: clear() must reset the render clock, otherwise a new
    # instance whose first reading has a lower timestamp stays hidden until the
    # stale clock catches up.
    w = AnalogInWidget(_sig())
    w.update_value(1000.0, ts=100.0)  # old instance, clock far ahead
    w.clear()  # instance switch
    w.update_value(2000.0, ts=0.5)  # new instance, lower timestamp
    assert w.sparkline_str(2)[-1] != " "  # new reading visible at the right edge


def _dsig(**kw) -> DigitalIn:
    base = dict(id="run", type="digital_in", title="Bilge", pgn=127501,
                field="Indicator1", on_label="RUN", off_label="OFF")
    base.update(kw)
    return DigitalIn(**base)


def test_digital_update_value_with_ts_feeds_step_history() -> None:
    w = DigitalInWidget(_dsig())
    w.update_value(False, ts=0.0)
    w.update_value(True, ts=1.0)
    w.update_value(True, ts=2.0)
    assert w.sparkline_str(3) == "▁██"


def test_digital_clear_empties_history() -> None:
    w = DigitalInWidget(_dsig())
    w.update_value(True, ts=0.0)
    w.clear()
    assert w.sparkline_str(2) == "  "


def test_digital_clear_resets_clock() -> None:
    # Same instance-switch clock-reset guard as AnalogInWidget.
    w = DigitalInWidget(_dsig())
    w.update_value(True, ts=100.0)
    w.clear()
    w.update_value(True, ts=0.5)
    assert w.sparkline_str(2)[-1] != " "


def test_digital_is_focusable() -> None:
    assert DigitalInWidget(_dsig()).can_focus is True
