from pgntui.signals.base import DigitalIn
from pgntui.signals.widgets import DigitalInWidget


def _sig() -> DigitalIn:
    return DigitalIn(
        id="bilge",
        type="digital_in",
        title="Bilge",
        pgn=127501,
        field="Indicator1",
        on_label="ON",
        off_label="OFF",
    )


def test_off_state() -> None:
    w = DigitalInWidget(_sig())
    w.update_value(False)
    assert "OFF" in w.render_text()
    assert "○" in w.render_text()


def test_on_state() -> None:
    w = DigitalInWidget(_sig())
    w.update_value(True)
    assert "ON" in w.render_text()
    assert "●" in w.render_text()
