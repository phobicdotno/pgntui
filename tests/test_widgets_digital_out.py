from pgntui.signals.base import DigitalOut
from pgntui.signals.widgets import DigitalOutWidget


def _sig() -> DigitalOut:
    return DigitalOut(
        id="anchor", type="digital_out", title="Anchor Light",
        pgn=127502, field="Indicator1",
        on_label="ON", off_label="OFF",
        write_pgn=127502, write_field="Indicator1",
    )


def test_disabled_when_write_disabled() -> None:
    w = DigitalOutWidget(_sig(), write_enabled=False)
    assert w.is_disabled
    w.toggle()
    assert w.value is False


def test_toggle_when_enabled() -> None:
    w = DigitalOutWidget(_sig(), write_enabled=True)
    pending: list[bool] = []
    w.on_write = pending.append
    w.toggle()
    assert w.value is True
    assert pending == [True]
    w.toggle()
    assert pending == [True, False]


def test_render_includes_state_brackets() -> None:
    w = DigitalOutWidget(_sig(), write_enabled=True)
    assert "[○ OFF]" in w.render_text()
    w.toggle()
    assert "[● ON]" in w.render_text()
