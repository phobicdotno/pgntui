"""Actisense NGT-1 BST protocol.

Framing and command bytes verified against the canboat actisense-serial
reference (actisense.h + actisense-serial.c):

- Messages are delimited by ``DLE STX`` … ``DLE ETX``.
- Only ``DLE`` (0x10) is escaped, by doubling. Bare STX/ETX in the body are
  literal; they are control bytes only when preceded by DLE.
- Body = ``command, length, payload…, checksum`` where
  ``checksum = (256 - (command + length + sum(payload))) & 0xFF``.
- ``N2K_MSG_RECEIVED = 0x93`` (NGT-1 → PC), ``N2K_MSG_SEND = 0x94`` (PC → NGT-1).
- Send payload: ``priority, PGN(3 LE), destination, length, data`` — no source,
  no timestamp (the device fills those).
"""

from unittest.mock import MagicMock

from pgntui.drivers.actisense import (
    DLE,
    ETX,
    N2K_MSG_RECEIVED,
    N2K_MSG_SEND,
    STX,
    MessageReassembler,
    NGT1Driver,
    build_n2k_received,
    build_n2k_send,
    frame_message,
    parse_n2k_received,
)
from pgntui.drivers.base import Capability, Frame


def test_capabilities() -> None:
    d = NGT1Driver()
    assert {Capability.READ, Capability.WRITE} <= d.capabilities


def test_frame_message_delimiters_and_checksum() -> None:
    framed = frame_message(0x94, bytes([0x01, 0x02]))
    # DLE STX ... DLE ETX
    assert framed[:2] == bytes([DLE, STX])
    assert framed[-2:] == bytes([DLE, ETX])
    # checksum: command + len + payload, negated
    expected_csum = (256 - (0x94 + 2 + 0x01 + 0x02)) & 0xFF
    # strip framing, undouble DLE
    inner = framed[2:-2]
    undoubled = bytearray()
    i = 0
    while i < len(inner):
        if inner[i] == DLE and i + 1 < len(inner) and inner[i + 1] == DLE:
            undoubled.append(DLE)
            i += 2
        else:
            undoubled.append(inner[i])
            i += 1
    assert undoubled[0] == 0x94
    assert undoubled[1] == 2
    assert undoubled[-1] == expected_csum


def test_frame_message_doubles_dle_in_body() -> None:
    # A payload byte equal to DLE must be doubled inside the frame.
    framed = frame_message(N2K_MSG_SEND, bytes([DLE]))
    body = framed[2:-2]
    assert body.count(DLE) >= 2  # the literal DLE payload byte is doubled


def test_build_n2k_send_layout() -> None:
    data = bytes(range(8))
    framed = build_n2k_send(prio=2, pgn=127488, dst=255, data=data)
    # Decode body
    inner = framed[2:-2]
    undoubled = bytearray()
    i = 0
    while i < len(inner):
        if inner[i] == DLE and i + 1 < len(inner) and inner[i + 1] == DLE:
            undoubled.append(DLE)
            i += 2
        else:
            undoubled.append(inner[i])
            i += 1
    command, length = undoubled[0], undoubled[1]
    payload = undoubled[2 : 2 + length]
    assert command == N2K_MSG_SEND
    assert payload[0] == 2  # priority
    assert payload[1] | (payload[2] << 8) | (payload[3] << 16) == 127488
    assert payload[4] == 255  # destination
    assert payload[5] == len(data)  # length
    assert bytes(payload[6:]) == data
    # No source / timestamp: total payload is 6 + len(data)
    assert length == 6 + len(data)


def test_reassembler_extracts_received_message() -> None:
    data = bytes([0x00, 0x98, 0x21, 0x0C, 0x00, 0x00, 0xFF, 0xFF])
    framed = build_n2k_received(prio=2, pgn=127488, dst=255, src=23, ts_ms=1500, data=data)
    r = MessageReassembler()
    # Feed split across chunks to exercise the state machine.
    msgs = r.push(framed[:5]) + r.push(framed[5:])
    assert len(msgs) == 1
    command, payload = msgs[0]
    assert command == N2K_MSG_RECEIVED
    frame = parse_n2k_received(payload)
    assert isinstance(frame, Frame)
    assert frame.pgn == 127488
    assert frame.source_addr == 23
    assert frame.destination == 255
    assert frame.data == data
    assert abs(frame.timestamp - 1.5) < 1e-9


def test_reassembler_ignores_bare_stx_etx_in_body() -> None:
    # Payload containing raw STX and ETX bytes must survive intact (they are
    # only control bytes when preceded by DLE).
    data = bytes([STX, ETX, STX, ETX, 0x00, 0x00, 0x00, 0x00])
    framed = build_n2k_received(prio=0, pgn=127488, dst=255, src=10, ts_ms=0, data=data)
    r = MessageReassembler()
    msgs = r.push(framed)
    assert len(msgs) == 1
    frame = parse_n2k_received(msgs[0][1])
    assert frame is not None
    assert frame.data == data


def test_reassembler_drops_bad_checksum() -> None:
    framed = bytearray(
        build_n2k_received(prio=0, pgn=127488, dst=255, src=1, ts_ms=0, data=b"\x00" * 8)
    )
    # Corrupt the checksum byte (second from the end, before DLE ETX).
    framed[-3] ^= 0xFF
    r = MessageReassembler()
    msgs = r.push(bytes(framed))
    # Structurally complete but checksum fails -> reassembler drops it entirely.
    assert msgs == []


def test_write_frame_uses_send_command() -> None:
    d = NGT1Driver()
    d._serial = MagicMock()
    f = Frame(timestamp=0.0, source_addr=42, pgn=127488, destination=255, data=b"\x00" * 8)
    d.write_frame(f)
    written = d._serial.write.call_args[0][0]
    assert written[:2] == bytes([DLE, STX])
    assert written[-2:] == bytes([DLE, ETX])
    # Decode command byte (first body byte, not a doubled DLE here).
    assert written[2] == N2K_MSG_SEND
