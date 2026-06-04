import json
from pathlib import Path

import pytest

from pgntui.signals.base import (
    AnalogIn,
    AnalogOut,
    DigitalIn,
    DigitalOut,
    Signal,
    SignalLoadError,
    load_signal,
    load_signals_dir,
)


def _write(tmp: Path, name: str, payload: dict) -> Path:
    p = tmp / name
    p.write_text(json.dumps(payload))
    return p


def test_load_analog_in(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "rpm.json",
        {
            "id": "engine_rpm_port",
            "type": "analog_in",
            "title": "Port RPM",
            "unit": "rpm",
            "pgn": 127488,
            "field": "Engine Speed",
            "source": 0,
            "instance": 0,
            "min": 0,
            "max": 6000,
            "decimals": 0,
            "warn_above": 5500,
            "alarm_above": 5800,
            "smoothing": 0.25,
            "log": True,
        },
    )
    sig = load_signal(p)
    assert isinstance(sig, AnalogIn)
    assert sig.id == "engine_rpm_port"
    assert sig.min == 0
    assert sig.max == 6000
    assert sig.smoothing == 0.25
    assert sig.log is True


def test_load_analog_out_requires_write_pgn(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "ap.json",
        {
            "id": "ap_heading",
            "type": "analog_out",
            "title": "Autopilot Heading",
            "pgn": 65360,
            "field": "Heading",
            "min": 0,
            "max": 359,
            "write_pgn": 65360,
            "write_field": "Heading",
        },
    )
    sig = load_signal(p)
    assert isinstance(sig, AnalogOut)
    assert sig.write_pgn == 65360
    assert sig.write_field == "Heading"


def test_load_digital_in(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "bilge.json",
        {
            "id": "bilge_pump",
            "type": "digital_in",
            "title": "Bilge Pump",
            "pgn": 127501,
            "field": "Indicator1",
            "on_label": "ON",
            "off_label": "OFF",
        },
    )
    sig = load_signal(p)
    assert isinstance(sig, DigitalIn)
    assert sig.on_label == "ON"


def test_load_digital_out(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "anchor.json",
        {
            "id": "anchor_light",
            "type": "digital_out",
            "title": "Anchor Light",
            "pgn": 127502,
            "field": "Indicator1",
            "write_pgn": 127502,
            "write_field": "Indicator1",
        },
    )
    sig = load_signal(p)
    assert isinstance(sig, DigitalOut)
    assert sig.write_pgn == 127502


def test_load_signal_rejects_unknown_type(tmp_path: Path) -> None:
    p = _write(tmp_path, "bad.json", {"id": "x", "type": "nope", "pgn": 1, "field": "f"})
    with pytest.raises(SignalLoadError):
        load_signal(p)


def test_analog_out_missing_write_pgn_fails(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "ap.json",
        {
            "id": "ap",
            "type": "analog_out",
            "title": "AP",
            "pgn": 1,
            "field": "f",
            "min": 0,
            "max": 1,
        },
    )
    with pytest.raises(SignalLoadError):
        load_signal(p)


def test_load_signals_dir(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "a.json",
        {
            "id": "a",
            "type": "analog_in",
            "title": "A",
            "pgn": 1,
            "field": "f",
            "min": 0,
            "max": 1,
        },
    )
    _write(
        tmp_path,
        "b.json",
        {
            "id": "b",
            "type": "digital_in",
            "title": "B",
            "pgn": 2,
            "field": "g",
        },
    )
    sigs = load_signals_dir(tmp_path)
    assert {s.id for s in sigs} == {"a", "b"}
    assert all(isinstance(s, Signal) for s in sigs)
