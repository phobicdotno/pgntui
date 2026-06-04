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


def test_smoothing_ema_step_converges_to_input() -> None:
    """Feeding a constant value must drive the EMA to that value.

    Previously the widget stored the already-blended ``displayed_value``
    back into ``_raw`` so each call re-smoothed the smoothed output,
    causing exponential lag and convergence below the true input.
    With the fix, ``_raw`` holds the most recent raw sample, so a
    held-constant input pulls the EMA cleanly toward it.
    """
    alpha = 0.9  # heavy smoothing — bug would lag badly here
    w = AnalogInWidget(_sig(smoothing=alpha))
    w.update_value(0.0)
    target = 10.0
    prev = w.displayed_value
    for _ in range(30):
        w.update_value(target)
        # Monotonically increasing toward the target.
        assert w.displayed_value >= prev - 1e-9
        # Never overshoots a held-constant input.
        assert w.displayed_value <= target + 1e-9
        prev = w.displayed_value
    # After ~30 samples with alpha=0.9 the correct EMA reaches the
    # input. The buggy version would still be stuck below ~9.6.
    assert abs(w.displayed_value - target) < 0.01


def test_smoothing_ema_first_sample_is_raw() -> None:
    """First sample bypasses smoothing (no prior raw to blend with)."""
    w = AnalogInWidget(_sig(smoothing=0.9))
    w.update_value(42.0)
    assert w.displayed_value == 42.0


def test_smoothing_ema_uses_raw_not_blended() -> None:
    """Regression: the EMA blends against the previous raw sample, not
    the previous smoothed output. Step from 0 to 10 with alpha=0.5
    must put displayed_value at exactly 5.0 on the transition (0.5*0
    + 0.5*10), and at exactly 7.5 on the next constant sample
    (0.5*10 + 0.5*10 = 10 if raw stored correctly... wait, the
    formula is a*prev_raw + (1-a)*new_value, so on the third sample
    with raw=10 and value=10 we get exactly 10)."""
    w = AnalogInWidget(_sig(smoothing=0.5))
    w.update_value(0.0)
    assert w.displayed_value == 0.0
    w.update_value(10.0)
    # 0.5*0 + 0.5*10 = 5.0
    assert abs(w.displayed_value - 5.0) < 1e-9
    w.update_value(10.0)
    # With the fix: 0.5*10 (prev raw) + 0.5*10 = 10.0.
    # With the bug: 0.5*5 (prev displayed) + 0.5*10 = 7.5.
    assert abs(w.displayed_value - 10.0) < 1e-9


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
