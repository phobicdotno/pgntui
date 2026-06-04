import pytest

from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget


def _sig(**kw) -> AnalogIn:
    base = dict(
        id="rpm",
        type="analog_in",
        title="RPM",
        pgn=127488,
        field="Engine Speed",
        unit="rpm",
        min=0.0,
        max=6000.0,
        decimals=0,
        warn_above=5500,
        alarm_above=5800,
    )
    base.update(kw)
    return AnalogIn(**base)


def test_state_thresholds() -> None:
    w = AnalogInWidget(_sig())
    assert w.compute_state(1000) == "ok"
    assert w.compute_state(5600) == "warn"
    assert w.compute_state(5900) == "alarm"


def test_smoothing_ema() -> None:
    w = AnalogInWidget(_sig(smoothing=0.5))
    w.update_value(1000)
    w.update_value(2000)
    assert 1400 <= w.displayed_value <= 1600


@pytest.mark.asyncio
async def test_render_nominal_snapshot() -> None:
    w = AnalogInWidget(_sig())
    w.update_value(2150)
    assert "RPM" in w.render_text()
    assert "2150" in w.render_text()


@pytest.mark.asyncio
async def test_render_alarm_marks_state() -> None:
    w = AnalogInWidget(_sig())
    w.update_value(5900)
    assert "alarm" in w.state_class
