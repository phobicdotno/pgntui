"""Display scale/offset on analog_in signals.

Canboat decodes SI base units (radians, m/s, Pa, K). Dashboards want
degrees, knots, Bar, Celsius. ``scale``/``offset`` transform the decoded
value for display: ``shown = decoded * scale + offset``.
"""

from __future__ import annotations

import json
from pathlib import Path

from pgntui.signals.base import AnalogIn, load_signal
from pgntui.signals.widgets import AnalogInWidget

RAD_TO_DEG = 57.29577951308232


def _heading(scale: float = RAD_TO_DEG, offset: float = 0.0) -> AnalogIn:
    return AnalogIn(
        id="hdg",
        type="analog_in",
        title="Magnetic heading",
        pgn=127250,
        field="Heading",
        unit="°",
        min=0,
        max=360,
        decimals=1,
        scale=scale,
        offset=offset,
    )


def test_loader_parses_scale_and_offset(tmp_path: Path) -> None:
    p = tmp_path / "hdg.json"
    p.write_text(
        json.dumps(
            {
                "id": "hdg",
                "type": "analog_in",
                "title": "Magnetic heading",
                "unit": "°",
                "pgn": 127250,
                "field": "Heading",
                "min": 0,
                "max": 360,
                "scale": RAD_TO_DEG,
                "offset": 0.0,
            }
        ),
        encoding="utf-8",
    )
    sig = load_signal(p)
    assert isinstance(sig, AnalogIn)
    assert sig.scale == RAD_TO_DEG
    assert sig.offset == 0.0


def test_loader_defaults_scale_one_offset_zero(tmp_path: Path) -> None:
    p = tmp_path / "plain.json"
    p.write_text(
        json.dumps(
            {
                "id": "plain",
                "type": "analog_in",
                "title": "Plain",
                "pgn": 128267,
                "field": "Depth",
            }
        ),
        encoding="utf-8",
    )
    sig = load_signal(p)
    assert isinstance(sig, AnalogIn)
    assert sig.scale == 1.0
    assert sig.offset == 0.0


def test_widget_applies_scale_to_displayed_value() -> None:
    w = AnalogInWidget(_heading())
    w.update_value(2.4609)  # radians ≈ 141.0°
    assert abs(w.displayed_value - 141.0) < 0.05
    assert "141.0" in w.render_text()


def test_widget_applies_offset_kelvin_to_celsius() -> None:
    sig = AnalogIn(
        id="wt",
        type="analog_in",
        title="Water Temp",
        pgn=130310,
        field="Water Temperature",
        unit="C",
        min=-5,
        max=40,
        decimals=1,
        offset=-273.15,
    )
    w = AnalogInWidget(sig)
    w.update_value(288.15)  # Kelvin
    assert abs(w.displayed_value - 15.0) < 1e-9


def test_alarm_thresholds_compare_in_display_units() -> None:
    sig = AnalogIn(
        id="hdg2",
        type="analog_in",
        title="Hdg",
        pgn=127250,
        field="Heading",
        min=0,
        max=360,
        scale=RAD_TO_DEG,
        warn_above=180.0,
    )
    w = AnalogInWidget(sig)
    w.update_value(3.49)  # ≈ 200° — above the 180° warn threshold
    assert w.state_class == "state-warn"
