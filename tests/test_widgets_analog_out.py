import pytest

from pgntui.signals.base import AnalogOut
from pgntui.signals.widgets import AnalogOutWidget


def _sig() -> AnalogOut:
    return AnalogOut(
        id="ap",
        type="analog_out",
        title="AP Heading",
        pgn=65360,
        field="Heading",
        unit="deg",
        min=0.0,
        max=359.0,
        decimals=0,
        write_pgn=65360,
        write_field="Heading",
    )


def test_disabled_when_write_disabled() -> None:
    w = AnalogOutWidget(_sig(), write_enabled=False)
    assert w.is_disabled
    assert "[set]" not in w.render_text()


def test_enabled_shows_set() -> None:
    w = AnalogOutWidget(_sig(), write_enabled=True)
    assert not w.is_disabled
    assert "[set]" in w.render_text()


@pytest.mark.asyncio
async def test_set_dialog_submits_value() -> None:
    w = AnalogOutWidget(_sig(), write_enabled=True)
    pending: list[float] = []
    w.on_write = pending.append
    w.submit_set(142.0)
    assert pending == [142.0]
