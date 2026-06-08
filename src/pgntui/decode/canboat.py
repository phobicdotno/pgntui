"""Thin wrapper around the bundled canboat pgns.json database.

To find the raw canboat field names for a given PGN, grep the bundled DB:
    grep -A5 '"PGN":127488' src/pgntui/decode/pgns.json | grep '"Name"'
The decoded dict carries the canonical canboat ``Name`` plus any alias from
``_FIELD_ALIASES`` (see below), so router bindings can use either.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from pgntui.decode.fastpacket import FastPacketReassembler, load_fast_packet_pgns
from pgntui.drivers.base import Frame


@dataclass(frozen=True, slots=True)
class DecodedFrame:
    timestamp: float
    source_addr: int
    pgn: int
    name: str | None
    fields: dict[str, Any] = field(default_factory=dict)


def frame_instance(df: DecodedFrame) -> int | None:
    """The frame's NMEA ``Instance`` value, or ``None`` if it carries no integer
    Instance. Used to split one PGN/source that reports several instances (e.g.
    several engines) into a row/box per instance instead of one that shows only
    the last-seen instance. (``bool`` is excluded — it's an ``int`` subclass.)"""
    value = df.fields.get("Instance")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


# Bridge between canboat's raw ``Name`` and the more common downstream name used
# by tools such as SignalK and most N2K reference docs. Keyed by
# ``(pgn, canboat field name)``.
#
# How to extend:
#     Add a row ``(pgn, "Raw Name"): "Common Name"`` when the canboat name is
#     confusing or differs from the stable name users see elsewhere.
#
# When to use:
#     Only when the raw name is genuinely ambiguous AND a widely-accepted
#     alternative exists. Don't add aliases just to mirror personal preference.
#
# Caveat:
#     The decoder emits BOTH the raw and the aliased name in the decoded dict,
#     so router bindings can match on either. Aliases are additive, never
#     destructive.
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
        # Fast-packet reassembly: PGNs whose declared payload exceeds 8 bytes
        # arrive as a sequence of CAN frames. The reassembler buffers them and
        # yields the complete payload only when all frames have been received.
        # For single-frame PGNs (the common case) the reassembler is a no-op
        # passthrough, so this is backwards compatible with the previous API.
        self._reassembler = FastPacketReassembler(load_fast_packet_pgns(db))

    @classmethod
    def load_bundled(cls) -> CanboatDecoder:
        with (
            resources.files("pgntui.decode").joinpath("pgns.json").open("r", encoding="utf-8") as fh
        ):
            return cls(json.load(fh))

    def has_pgn(self, pgn: int) -> bool:
        return pgn in self._by_pgn

    def decode(self, frame: Frame) -> DecodedFrame | None:
        """Decode a single CAN frame.

        For single-frame PGNs this behaves as before: parse fields out of the
        frame's data and return a :class:`DecodedFrame`.

        For fast-packet PGNs the frame is fed through the internal
        :class:`FastPacketReassembler`. The first N-1 frames of a fast-packet
        message return ``None`` (waiting for more frames); the final frame
        returns the fully assembled :class:`DecodedFrame`.
        """
        entries = self._by_pgn.get(frame.pgn)
        if not entries:
            return None
        payloads = list(self._reassembler.push(frame.pgn, frame.source_addr, frame.data))
        if not payloads:
            return None
        entry = entries[0]
        payload = payloads[0]
        fields = self._decode_fields(entry, payload, frame.pgn)
        return DecodedFrame(
            timestamp=frame.timestamp,
            source_addr=frame.source_addr,
            pgn=frame.pgn,
            name=entry.get("Description") or entry.get("Id"),
            fields=fields,
        )

    def _decode_fields(self, entry: dict[str, Any], data: bytes, pgn: int) -> dict[str, Any]:
        out: dict[str, Any] = {}
        bit_offset = 0
        for f in entry.get("Fields", []) or entry.get("fields", []) or []:
            size = int(
                f.get("BitLength") or f.get("bitLength") or f.get("Length") or f.get("length") or 0
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
            offset_raw = f.get("Offset")
            if offset_raw is None:
                offset_raw = f.get("offset")
            try:
                offset = float(offset_raw) if offset_raw is not None else 0.0
            except (TypeError, ValueError):
                offset = 0.0
            signed = bool(f.get("Signed") or f.get("signed"))
            if signed and raw >= (1 << (size - 1)):
                raw -= 1 << size
            # Canboat formula: value = raw * resolution + offset.
            # Keep the int fast-path when both transforms are no-ops so callers
            # that expect integer enum/lookup values aren't surprised.
            if resolution == 1.0 and offset == 0.0:
                value: Any = raw
            else:
                value = raw * resolution + offset
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


__all__ = ["CanboatDecoder", "DecodedFrame", "frame_instance"]
