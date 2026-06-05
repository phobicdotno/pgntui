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
    """Inbound analog signal binding.

    Note on ``smoothing``: this field weights the **previous** sample, not the
    new one. The display blends as::

        shown = smoothing * prev_raw + (1.0 - smoothing) * new

    So ``smoothing=0.0`` means no smoothing (raw passthrough) and
    ``smoothing=1.0`` freezes the value at the first sample. This is the
    opposite convention of textbook EMA ``alpha``, which weights the NEW
    sample. Express your value accordingly when porting from references.

    ``scale``/``offset`` convert the decoded value into display units
    (``shown = decoded * scale + offset``). Canboat decodes SI base units —
    radians, m/s, Pa, K — so e.g. ``scale=57.29578`` renders degrees and
    ``offset=-273.15`` renders Celsius. ``min``/``max`` and the warn/alarm
    thresholds are expressed in display units.
    """

    unit: str | None = None
    min: float = 0.0
    max: float = 1.0
    decimals: int = 0
    warn_above: float | None = None
    alarm_above: float | None = None
    warn_below: float | None = None
    alarm_below: float | None = None
    smoothing: float = 0.0
    scale: float = 1.0
    offset: float = 0.0


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
    """Inbound boolean signal binding.

    ``bit`` selects a single bit out of an integer bitfield value
    (``shown = (decoded >> bit) & 1``) — used for status PGNs such as
    127489 Discrete Status 1/2 where each flag is one bit. ``None`` keeps
    the plain truthiness behaviour for fields that are already boolean.
    """

    on_label: str = "ON"
    off_label: str = "OFF"
    bit: int | None = None


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
        payload = json.loads(path.read_text(encoding="utf-8"))
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
            warn_above=float(payload["warn_above"]) if "warn_above" in payload else None,
            alarm_above=float(payload["alarm_above"]) if "alarm_above" in payload else None,
            warn_below=float(payload["warn_below"]) if "warn_below" in payload else None,
            alarm_below=float(payload["alarm_below"]) if "alarm_below" in payload else None,
            smoothing=float(payload.get("smoothing", 0.0)),
            scale=float(payload.get("scale", 1.0)),
            offset=float(payload.get("offset", 0.0)),
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
            warn_above=float(payload["warn_above"]) if "warn_above" in payload else None,
            alarm_above=float(payload["alarm_above"]) if "alarm_above" in payload else None,
            warn_below=float(payload["warn_below"]) if "warn_below" in payload else None,
            alarm_below=float(payload["alarm_below"]) if "alarm_below" in payload else None,
            write_pgn=int(payload["write_pgn"]),
            write_field=payload["write_field"],
        )
    if t == "digital_in":
        return DigitalIn(
            **common,
            on_label=payload.get("on_label", "ON"),
            off_label=payload.get("off_label", "OFF"),
            bit=int(payload["bit"]) if "bit" in payload else None,
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
