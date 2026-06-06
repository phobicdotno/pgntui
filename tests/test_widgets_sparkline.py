from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget


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
    assert w.sparkline_str(3)[-1] != " "  # data at the right edge
    w.tick(10.0)  # far enough that bucket 0 scrolls outside the 3-col window
    assert w.sparkline_str(3) == "   "  # all gaps: old data scrolled out


def test_clear_empties_history_keeps_expanded() -> None:
    w = AnalogInWidget(_sig())
    w.update_value(1000.0, ts=0.0)
    w.toggle_sparkline()
    w.clear()
    assert w.expanded is True
    assert w.sparkline_str(2) == "  "


def test_is_focusable() -> None:
    assert AnalogInWidget(_sig()).can_focus is True
