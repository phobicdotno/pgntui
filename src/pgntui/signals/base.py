"""Signal dataclasses and JSON loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SignalLoadError(ValueError):
    """Raised when a signal JSON document is invalid."""


@dataclass(frozen=True, slots=True)
class Signal:
    id: str
    type: str
    title: str
    pgn: int
    field: str
    source: int | None = None
    instance: int | None = None
    log: bool = False


@dataclass(frozen=True, slots=True)
class AnalogIn(Signal):
    unit: str | None = None
    min: float = 0.0
    max: float = 1.0
    decimals: int = 0
    warn_above: float | None = None
    alarm_above: float | None = None
    warn_below: float | None = None
    alarm_below: float | None = None
    smoothing: float = 0.0


@dataclass(frozen=True, slots=True)
class AnalogOut(Signal):
    unit: str | None = None
    min: float = 0.0
    max: float = 1.0
    decimals: int = 0
    warn_above: float | None = None
    alarm_above: float | None = None
    warn_below: float | None = None
    alarm_below: float | None = None
    write_pgn: int = 0
    write_field: str = ""


@dataclass(frozen=True, slots=True)
class DigitalIn(Signal):
    on_label: str = "ON"
    off_label: str = "OFF"


@dataclass(frozen=True, slots=True)
class DigitalOut(Signal):
    on_label: str = "ON"
    off_label: str = "OFF"
    write_pgn: int = 0
    write_field: str = ""


_COMMON = {"id", "type", "title", "pgn", "field", "source", "instance", "log"}


def _common(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": payload["id"],
        "type": payload["type"],
        "title": payload["title"],
        "pgn": int(payload["pgn"]),
        "field": payload["field"],
        "source": payload.get("source"),
        "instance": payload.get("instance"),
        "log": bool(payload.get("log", False)),
    }


def load_signal(path: Path) -> Signal:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise SignalLoadError(f"{path}: invalid JSON: {e}") from e
    t = payload.get("type")
    try:
        common = _common(payload)
    except KeyError as e:
        raise SignalLoadError(f"{path}: missing key {e}") from e
    if t == "analog_in":
        return AnalogIn(
            **common,
            unit=payload.get("unit"),
            min=float(payload.get("min", 0.0)),
            max=float(payload.get("max", 1.0)),
            decimals=int(payload.get("decimals", 0)),
            warn_above=payload.get("warn_above"),
            alarm_above=payload.get("alarm_above"),
            warn_below=payload.get("warn_below"),
            alarm_below=payload.get("alarm_below"),
            smoothing=float(payload.get("smoothing", 0.0)),
        )
    if t == "analog_out":
        if "write_pgn" not in payload or "write_field" not in payload:
            raise SignalLoadError(f"{path}: analog_out requires write_pgn + write_field")
        return AnalogOut(
            **common,
            unit=payload.get("unit"),
            min=float(payload.get("min", 0.0)),
            max=float(payload.get("max", 1.0)),
            decimals=int(payload.get("decimals", 0)),
            warn_above=payload.get("warn_above"),
            alarm_above=payload.get("alarm_above"),
            warn_below=payload.get("warn_below"),
            alarm_below=payload.get("alarm_below"),
            write_pgn=int(payload["write_pgn"]),
            write_field=payload["write_field"],
        )
    if t == "digital_in":
        return DigitalIn(
            **common,
            on_label=payload.get("on_label", "ON"),
            off_label=payload.get("off_label", "OFF"),
        )
    if t == "digital_out":
        if "write_pgn" not in payload or "write_field" not in payload:
            raise SignalLoadError(f"{path}: digital_out requires write_pgn + write_field")
        return DigitalOut(
            **common,
            on_label=payload.get("on_label", "ON"),
            off_label=payload.get("off_label", "OFF"),
            write_pgn=int(payload["write_pgn"]),
            write_field=payload["write_field"],
        )
    raise SignalLoadError(f"{path}: unknown signal type {t!r}")


def load_signals_dir(directory: Path) -> list[Signal]:
    out: list[Signal] = []
    for p in sorted(directory.glob("*.json")):
        out.append(load_signal(p))
    return out


__all__ = [
    "AnalogIn",
    "AnalogOut",
    "DigitalIn",
    "DigitalOut",
    "Signal",
    "SignalLoadError",
    "load_signal",
    "load_signals_dir",
]
