"""Per-bit extraction on digital_in signals.

Engine/transmission status PGNs (127489 Discrete Status 1/2, 127493
Discrete Status 1) decode as integer bitfields. ``bit`` selects a single
bit so each status lamp can bind to one flag:
``shown = (decoded >> bit) & 1``.
"""

from __future__ import annotations

import json
from pathlib import Path

from pgntui.app import PgntuiApp
from pgntui.signals.base import DigitalIn, load_signal
from pgntui.signals.widgets import DigitalInWidget


def _check_engine(bit: int | None = 0) -> DigitalIn:
    return DigitalIn(
        id="check_engine",
        type="digital_in",
        title="Check engine",
        pgn=127489,
        field="Discrete Status 1",
        bit=bit,
    )


def test_loader_parses_bit(tmp_path: Path) -> None:
    p = tmp_path / "check_engine.json"
    p.write_text(
        json.dumps(
            {
                "id": "check_engine",
                "type": "digital_in",
                "title": "Check engine",
                "pgn": 127489,
                "field": "Discrete Status 1",
                "bit": 11,
            }
        ),
        encoding="utf-8",
    )
    sig = load_signal(p)
    assert isinstance(sig, DigitalIn)
    assert sig.bit == 11


def test_loader_defaults_bit_none(tmp_path: Path) -> None:
    p = tmp_path / "plain.json"
    p.write_text(
        json.dumps(
            {
                "id": "plain",
                "type": "digital_in",
                "title": "Plain",
                "pgn": 127501,
                "field": "Indicator1",
            }
        ),
        encoding="utf-8",
    )
    sig = load_signal(p)
    assert isinstance(sig, DigitalIn)
    assert sig.bit is None


def test_widget_extracts_selected_bit() -> None:
    w = DigitalInWidget(_check_engine(bit=2))
    w.update_value(0b0100)
    assert w.value is True
    w.update_value(0b1011)  # bit 2 clear, others set
    assert w.value is False


def test_widget_without_bit_uses_truthiness() -> None:
    w = DigitalInWidget(_check_engine(bit=None))
    w.update_value(0)
    assert w.value is False
    w.update_value(1)
    assert w.value is True


def test_apply_update_preserves_bitfield_int() -> None:
    """The app's update path must hand the raw decoded int to the widget —
    coercing to bool before the widget sees it would destroy bit selection."""
    w = DigitalInWidget(_check_engine(bit=3))
    PgntuiApp._apply_update(w, 0b0111)  # bit 3 clear but value truthy
    assert w.value is False
    PgntuiApp._apply_update(w, 0b1000)
    assert w.value is True
