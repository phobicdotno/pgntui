from unittest.mock import MagicMock

from pgntui.drivers.actisense import (
    DLE,
    ETX,
    STX,
    NGT1Driver,
    build_n2k_message,
    escape_frame,
    parse_frame,
    unescape_frame,
)
from pgntui.drivers.base import Capability, Frame


def test_capabilities() -> None:
    d = NGT1Driver()
    assert {Capability.READ, Capability.WRITE} <= d.capabilities


def test_escape_unescape_roundtrip() -> None:
    payload = bytes([0x10, 0x02, 0x03, 0xAA])
    escaped = escape_frame(payload)
    assert escaped.count(DLE) == 4  # 3 escapes + framing-internal DLEs preserved
    assert unescape_frame(escaped) == payload


def test_parse_frame_pgn_127488() -> None:
    data = bytes([0x00, 0x98, 0x21, 0x0C, 0x00, 0x00, 0xFF, 0xFF])
    msg = build_n2k_message(prio=2, pgn=127488, dst=255, src=23, data=data)
    frame = bytes([STX]) + escape_frame(msg) + bytes([ETX])
    parsed = parse_frame(frame)
    assert isinstance(parsed, Frame)
    assert parsed.pgn == 127488
    assert parsed.source_addr == 23
    assert parsed.data == data


def test_write_frame_sends_serial() -> None:
    d = NGT1Driver()
    d._serial = MagicMock()  # bypass open()
    d.capabilities = {Capability.READ, Capability.WRITE}
    f = Frame(timestamp=0.0, source_addr=42, pgn=127488, data=b"\x00" * 8)
    d.write_frame(f)
    written = d._serial.write.call_args[0][0]
    assert written[0] == STX
    assert written[-1] == ETX
