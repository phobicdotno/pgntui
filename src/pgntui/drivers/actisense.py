"""Actisense NGT-1 driver."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

from pgntui.drivers.base import Capability, Frame

STX = 0x02
ETX = 0x03
DLE = 0x10
CMD_N2K_MSG = 0x93


def escape_frame(payload: bytes) -> bytes:
    out = bytearray()
    for b in payload:
        if b in (STX, ETX, DLE):
            out.append(DLE)
        out.append(b)
    return bytes(out)


def unescape_frame(payload: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(payload):
        if payload[i] == DLE and i + 1 < len(payload):
            out.append(payload[i + 1])
            i += 2
        else:
            out.append(payload[i])
            i += 1
    return bytes(out)


def _checksum(buf: bytes) -> int:
    return (256 - (sum(buf) & 0xFF)) & 0xFF


def build_n2k_message(prio: int, pgn: int, dst: int, src: int, data: bytes) -> bytes:
    body = bytearray()
    body.append(prio & 0xFF)
    body.append(pgn & 0xFF)
    body.append((pgn >> 8) & 0xFF)
    body.append((pgn >> 16) & 0xFF)
    body.append(dst & 0xFF)
    body.append(src & 0xFF)
    body += (0).to_bytes(4, "little")  # timestamp
    body.append(len(data))
    body += data
    framed = bytearray([CMD_N2K_MSG, len(body)]) + body
    framed.append(_checksum(bytes(framed)))
    return bytes(framed)


def parse_frame(raw: bytes) -> Frame | None:
    if len(raw) < 4 or raw[0] != STX or raw[-1] != ETX:
        return None
    inner = unescape_frame(raw[1:-1])
    if len(inner) < 3:
        return None
    cmd = inner[0]
    length = inner[1]
    body = inner[2 : 2 + length]
    if cmd != CMD_N2K_MSG or len(body) < 11:
        return None
    priority = body[0]
    pgn = body[1] | (body[2] << 8) | (body[3] << 16)
    dst = body[4]
    src = body[5]
    ts_ms = int.from_bytes(body[6:10], "little")
    data_len = body[10]
    data = bytes(body[11 : 11 + data_len])
    return Frame(
        timestamp=ts_ms / 1000.0,
        source_addr=src,
        pgn=pgn,
        data=data,
        priority=priority,
        destination=dst,
    )


class NGT1Driver:
    name = "actisense-ngt1"
    capabilities = {Capability.READ, Capability.WRITE}

    def __init__(self) -> None:
        self._serial: Any = None
        # Cooperative stop: ``close()`` sets this so ``read_frames`` can break
        # out of its blocking ``while True`` loop on the next iteration without
        # waiting for the underlying serial port to raise.
        self._stop: threading.Event = threading.Event()

    def open(self, config: dict[str, Any]) -> None:
        import serial  # type: ignore[import-untyped]  # pyserial has no stubs

        self._stop.clear()
        self._serial = serial.Serial(
            port=config["port"],
            baudrate=int(config.get("baud", 115200)),
            timeout=0.1,
        )

    def close(self) -> None:
        # Signal stop FIRST so a read_frames loop running on another thread
        # exits cleanly the next time around, rather than racing the close on
        # the underlying serial handle.
        self._stop.set()
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def read_frames(self) -> Iterator[Frame]:
        assert self._serial is not None
        buf = bytearray()
        in_frame = False
        while True:
            if self._stop.is_set():
                return
            byte = self._serial.read(1)
            if not byte:
                continue
            b = byte[0]
            if b == STX and not in_frame:
                in_frame = True
                buf = bytearray([STX])
                continue
            if in_frame:
                buf.append(b)
                if b == ETX and (len(buf) < 2 or buf[-2] != DLE):
                    in_frame = False
                    frame = parse_frame(bytes(buf))
                    if frame is not None:
                        yield frame

    def write_frame(self, frame: Frame) -> None:
        assert self._serial is not None
        msg = build_n2k_message(
            prio=frame.priority,
            pgn=frame.pgn,
            dst=frame.destination,
            src=frame.source_addr,
            data=frame.data,
        )
        self._serial.write(bytes([STX]) + escape_frame(msg) + bytes([ETX]))


__all__ = [
    "DLE",
    "ETX",
    "NGT1Driver",
    "STX",
    "build_n2k_message",
    "escape_frame",
    "parse_frame",
    "unescape_frame",
]
