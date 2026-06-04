"""Thin wrapper around the bundled canboat pgns.json database."""

from __future__ import annotations

import json
import struct  # noqa: F401  (retained for future tasks)
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from pgntui.drivers.base import Frame


@dataclass(frozen=True, slots=True)
class DecodedFrame:
    timestamp: float
    source_addr: int
    pgn: int
    name: str | None
    fields: dict[str, Any] = field(default_factory=dict)


# Aliases for field names that conventional tools (signalk etc.) expose
# differently from the bare canboat `Name`. Keyed by (pgn, canboat field name).
_FIELD_ALIASES: dict[tuple[int, str], str] = {
    (127488, "Speed"): "Engine Speed",
    (127488, "Boost Pressure"): "Engine Boost Pressure",
    (127488, "Tilt/Trim"): "Engine Tilt/Trim",
}


class CanboatDecoder:
    def __init__(self, db: dict[str, Any]) -> None:
        self._db = db
        pgn_list = db.get("PGNs") or db.get("pgns") or []
        self._by_pgn: dict[int, list[dict[str, Any]]] = {}
        for entry in pgn_list:
            pgn = int(entry.get("PGN") or entry.get("pgn") or 0)
            if pgn:
                self._by_pgn.setdefault(pgn, []).append(entry)

    @classmethod
    def load_bundled(cls) -> CanboatDecoder:
        with resources.files("pgntui.decode").joinpath("pgns.json").open(
            "r", encoding="utf-8"
        ) as fh:
            return cls(json.load(fh))

    def has_pgn(self, pgn: int) -> bool:
        return pgn in self._by_pgn

    def decode(self, frame: Frame) -> DecodedFrame | None:
        entries = self._by_pgn.get(frame.pgn)
        if not entries:
            return None
        entry = entries[0]
        fields = self._decode_fields(entry, frame.data, frame.pgn)
        return DecodedFrame(
            timestamp=frame.timestamp,
            source_addr=frame.source_addr,
            pgn=frame.pgn,
            name=entry.get("Description") or entry.get("Id"),
            fields=fields,
        )

    def _decode_fields(
        self, entry: dict[str, Any], data: bytes, pgn: int
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        bit_offset = 0
        for f in entry.get("Fields", []) or entry.get("fields", []) or []:
            size = int(
                f.get("BitLength")
                or f.get("bitLength")
                or f.get("Length")
                or f.get("length")
                or 0
            )
            if size <= 0:
                continue
            name = f.get("Name") or f.get("name") or "?"
            raw = _read_bits(data, bit_offset, size)
            resolution_raw = f.get("Resolution")
            if resolution_raw is None:
                resolution_raw = f.get("resolution")
            try:
                resolution = float(resolution_raw) if resolution_raw is not None else 1.0
            except (TypeError, ValueError):
                resolution = 1.0
            if resolution == 0:
                resolution = 1.0
            signed = bool(f.get("Signed") or f.get("signed"))
            if signed and raw >= (1 << (size - 1)):
                raw -= 1 << size
            value: Any = raw * resolution if resolution != 1.0 else raw
            out[name] = value
            alias = _FIELD_ALIASES.get((pgn, name))
            if alias:
                out[alias] = value
            bit_offset += size
        return out


def _read_bits(data: bytes, offset: int, length: int) -> int:
    result = 0
    for i in range(length):
        bit_index = offset + i
        byte_index = bit_index // 8
        bit_in_byte = bit_index % 8
        if byte_index >= len(data):
            break
        bit = (data[byte_index] >> bit_in_byte) & 1
        result |= bit << i
    return result


__all__ = ["CanboatDecoder", "DecodedFrame"]
