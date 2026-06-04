"""Unit tests for the NMEA 2000 fast-packet reassembler."""

from __future__ import annotations

import time
from collections.abc import Iterator
from unittest.mock import patch

from pgntui.decode.fastpacket import FastPacketReassembler, load_fast_packet_pgns


def _frame0(seq: int, length: int, payload: bytes) -> bytes:
    """Build a fast-packet frame 0 (frame counter == 0).

    Layout: [hdr=seq<<5 | 0] [length] [payload 6 bytes].
    """
    header = ((seq & 0x07) << 5) | 0x00
    chunk = (payload + b"\x00" * 6)[:6]
    return bytes([header, length]) + chunk


def _frame_n(seq: int, idx: int, payload: bytes) -> bytes:
    """Build a fast-packet continuation frame (frame counter == idx)."""
    assert idx >= 1
    header = ((seq & 0x07) << 5) | (idx & 0x1F)
    chunk = (payload + b"\x00" * 7)[:7]
    return bytes([header]) + chunk


def _collect(it: Iterator[bytes]) -> list[bytes]:
    return list(it)


def test_single_frame_passes_through() -> None:
    fp = FastPacketReassembler(fast_pgns={129029})
    data = bytes([0x00, 0x98, 0x21, 0x0C, 0x00, 0x00, 0xFF, 0xFF])
    # Non-fast PGN: returned unchanged.
    yielded = _collect(fp.push(pgn=127488, source=23, data=data))
    assert yielded == [data]


def test_first_frame_with_short_length_yields_immediately() -> None:
    fp = FastPacketReassembler(fast_pgns={129540})
    # length=3 fits entirely in frame 0 (frame 0 carries 6 useful bytes).
    payload = bytes([0xAA, 0xBB, 0xCC])
    f0 = _frame0(seq=1, length=3, payload=payload)
    yielded = _collect(fp.push(pgn=129540, source=10, data=f0))
    assert yielded == [payload]
    # Buffer must be empty after immediate yield.
    assert fp._buffers == {}


def test_three_frame_assembly() -> None:
    fp = FastPacketReassembler(fast_pgns={129029})
    # Construct a 20-byte fast-packet message: 6 bytes in frame 0, 7 in
    # frame 1, 7 in frame 2 -> 20 total.
    body = bytes(range(20))
    f0 = _frame0(seq=2, length=20, payload=body[0:6])
    f1 = _frame_n(seq=2, idx=1, payload=body[6:13])
    f2 = _frame_n(seq=2, idx=2, payload=body[13:20])
    # First two frames yield nothing.
    assert _collect(fp.push(pgn=129029, source=15, data=f0)) == []
    assert _collect(fp.push(pgn=129029, source=15, data=f1)) == []
    yielded = _collect(fp.push(pgn=129029, source=15, data=f2))
    assert yielded == [body]


def test_orphan_continuation_dropped() -> None:
    fp = FastPacketReassembler(fast_pgns={129029})
    # Continuation with no prior frame 0.
    f1 = _frame_n(seq=3, idx=1, payload=b"abcdefg")
    yielded = _collect(fp.push(pgn=129029, source=15, data=f1))
    assert yielded == []
    assert fp._buffers == {}


def test_out_of_order_drops_buffer() -> None:
    fp = FastPacketReassembler(fast_pgns={129029})
    f0 = _frame0(seq=1, length=20, payload=b"\x01\x02\x03\x04\x05\x06")
    # Skip frame 1, jump to frame 2.
    f2 = _frame_n(seq=1, idx=2, payload=b"abcdefg")
    assert _collect(fp.push(pgn=129029, source=42, data=f0)) == []
    assert _collect(fp.push(pgn=129029, source=42, data=f2)) == []
    # Buffer dropped.
    assert fp._buffers == {}


def test_new_sequence_id_replaces() -> None:
    fp = FastPacketReassembler(fast_pgns={129029})
    f0_seq1 = _frame0(seq=1, length=20, payload=b"\x01\x02\x03\x04\x05\x06")
    assert _collect(fp.push(pgn=129029, source=7, data=f0_seq1)) == []
    assert (7, 129029) in fp._buffers
    assert fp._buffers[(7, 129029)].sequence_id == 1

    # New message from same source, different seq id starts fresh.
    f0_seq2 = _frame0(seq=2, length=15, payload=b"\xaa\xbb\xcc\xdd\xee\xff")
    assert _collect(fp.push(pgn=129029, source=7, data=f0_seq2)) == []
    assert fp._buffers[(7, 129029)].sequence_id == 2
    assert fp._buffers[(7, 129029)].expected_length == 15


def test_mixed_sequence_continuation_drops_buffer() -> None:
    fp = FastPacketReassembler(fast_pgns={129029})
    f0 = _frame0(seq=1, length=20, payload=b"\x01\x02\x03\x04\x05\x06")
    # Continuation but with a different seq id (interleaved message from same sender).
    f1_wrong = _frame_n(seq=2, idx=1, payload=b"abcdefg")
    assert _collect(fp.push(pgn=129029, source=7, data=f0)) == []
    assert _collect(fp.push(pgn=129029, source=7, data=f1_wrong)) == []
    assert fp._buffers == {}


def test_stale_buffer_expires() -> None:
    fp = FastPacketReassembler(fast_pgns={129029}, timeout_s=1.0)
    f0 = _frame0(seq=1, length=20, payload=b"\x01\x02\x03\x04\x05\x06")

    with patch.object(time, "monotonic", return_value=1000.0):
        assert _collect(fp.push(pgn=129029, source=5, data=f0)) == []
        assert (5, 129029) in fp._buffers

    # Push another frame from a different sender after the timeout; the stale
    # buffer for source 5 must be evicted by the expire pass.
    with patch.object(time, "monotonic", return_value=1010.0):
        other = bytes([0x00, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE])
        assert _collect(fp.push(pgn=127488, source=99, data=other)) == [other]
        assert (5, 129029) not in fp._buffers


def test_two_sources_do_not_collide() -> None:
    fp = FastPacketReassembler(fast_pgns={129029})
    # Two senders pushing the same PGN simultaneously must not corrupt each
    # other's buffers because the key includes the source.
    f0_a = _frame0(seq=1, length=13, payload=b"AAAAAA")
    f0_b = _frame0(seq=1, length=13, payload=b"BBBBBB")
    f1_a = _frame_n(seq=1, idx=1, payload=b"AAAAAAA")
    f1_b = _frame_n(seq=1, idx=1, payload=b"BBBBBBB")
    assert _collect(fp.push(pgn=129029, source=1, data=f0_a)) == []
    assert _collect(fp.push(pgn=129029, source=2, data=f0_b)) == []
    out_a = _collect(fp.push(pgn=129029, source=1, data=f1_a))
    out_b = _collect(fp.push(pgn=129029, source=2, data=f1_b))
    assert out_a == [b"AAAAAA" + b"AAAAAAA"]
    assert out_b == [b"BBBBBB" + b"BBBBBBB"]


def test_malformed_frame_too_short_dropped() -> None:
    fp = FastPacketReassembler(fast_pgns={129029})
    # Less than 2 bytes — cannot read header + length.
    assert _collect(fp.push(pgn=129029, source=8, data=b"\x00")) == []
    assert _collect(fp.push(pgn=129029, source=8, data=b"")) == []


def test_load_fast_packet_pgns_recognises_type_field() -> None:
    db = {
        "PGNs": [
            {"PGN": 127488, "Type": "Single", "Length": 8},
            {"PGN": 129029, "Type": "Fast", "Length": 43},
            {"PGN": 129025, "Type": "Single", "Length": 8},
            {"PGN": 130306, "Type": "Fast", "Length": 6},  # Fast despite tiny Length
        ]
    }
    fast = load_fast_packet_pgns(db)
    assert fast == {129029, 130306}


def test_load_fast_packet_pgns_length_fallback() -> None:
    db = {
        "PGNs": [
            {"PGN": 111, "Length": 8},  # single
            {"PGN": 222, "Length": 12},  # fast (heuristic)
            {"PGN": 333, "MinLength": 20},  # fast (alt key)
            {"PGN": 444},  # no length info — single
        ]
    }
    fast = load_fast_packet_pgns(db)
    assert fast == {222, 333}


def test_load_fast_packet_pgns_handles_garbage() -> None:
    db = {
        "PGNs": [
            {"PGN": None},
            {"PGN": "not-an-int"},
            {"Type": "Fast"},  # no PGN
            {"PGN": 555, "Type": "Fast", "Length": "weird"},
        ]
    }
    fast = load_fast_packet_pgns(db)
    assert fast == {555}
