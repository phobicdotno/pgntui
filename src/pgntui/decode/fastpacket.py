"""NMEA 2000 fast-packet reassembly.

NMEA 2000 PGNs come in two flavors:

- **Single-frame**: payload <= 8 bytes, one CAN frame, decoded directly.
- **Fast-packet**: payload > 8 bytes, split across multiple CAN frames each
  carrying a 1-byte header with sequence + frame counters and 6 or 7 bytes of
  payload.

Header byte layout (`data[0]`):

- Bits 7..5: 3-bit sequence counter (0..7, wraps; identifies one *message* from
  the sender — distinct from CAN bus sequence).
- Bits 4..0: 5-bit frame counter (0..31) within a single message.

Frame 0 (frame counter == 0):
    ``[hdr] [total_length] [d0 d1 d2 d3 d4 d5]`` — 6 useful payload bytes.
Frame N (frame counter >= 1):
    ``[hdr] [d0 d1 d2 d3 d4 d5 d6]`` — 7 useful payload bytes.

Total payload length is declared in byte 1 of frame 0. The reassembler buffers
frames keyed by ``(source, pgn)`` until either all bytes are received or a
new sequence counter from the same source invalidates the buffer.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any


@dataclass
class _PacketState:
    expected_length: int
    received_bytes: bytearray
    next_frame_counter: int  # frame counter we expect next (0 was already received)
    sequence_id: int
    last_seen: float  # for stale-buffer expiry


class FastPacketReassembler:
    """Buffer fast-packet frames keyed by ``(source, pgn)`` until complete.

    Usage::

        fp = FastPacketReassembler(fast_pgns={129025, 129026, 129029, ...})
        for frame in driver.read_frames():
            for payload in fp.push(frame.pgn, frame.source_addr, frame.data):
                decoded = decoder.decode_payload(frame.pgn, payload)

    For PGNs *not* in ``fast_pgns`` the input data is yielded unchanged so the
    caller can use a single uniform code path. Stale buffers (no update within
    ``timeout_s``) are dropped on the next :meth:`push` call.
    """

    def __init__(self, fast_pgns: set[int], timeout_s: float = 5.0) -> None:
        self._fast_pgns = fast_pgns
        self._timeout_s = timeout_s
        self._buffers: dict[tuple[int, int], _PacketState] = {}

    def push(self, pgn: int, source: int, data: bytes) -> Iterator[bytes]:
        """Push one CAN frame's payload. Yield 0 or 1 complete payload(s).

        For single-frame PGNs (``pgn`` not in ``fast_pgns``): yields ``data``
        unchanged immediately. For fast-packet PGNs: yields the assembled
        payload only once the full message has been received.

        Args:
            pgn: NMEA 2000 PGN number.
            source: Source address of the sender (0..251).
            data: Raw CAN frame payload (typically 8 bytes).
        """
        now = time.monotonic()
        self._expire_stale(now)

        if pgn not in self._fast_pgns:
            yield data
            return

        if len(data) < 2:
            # Malformed fast-packet frame; cannot read header or first byte.
            return

        header = data[0]
        seq_id = (header >> 5) & 0x07
        frame_counter = header & 0x1F
        key = (source, pgn)

        if frame_counter == 0:
            # First frame: byte 1 is the total payload length, bytes 2..7 carry
            # the first 6 useful payload bytes.
            length = data[1]
            first_chunk = bytes(data[2:8])
            if length <= len(first_chunk):
                # Entire payload fit in frame 0.
                self._buffers.pop(key, None)
                yield first_chunk[:length]
                return
            self._buffers[key] = _PacketState(
                expected_length=length,
                received_bytes=bytearray(first_chunk),
                next_frame_counter=1,
                sequence_id=seq_id,
                last_seen=now,
            )
            return

        # Continuation frame.
        st = self._buffers.get(key)
        if st is None:
            # Orphan continuation with no anchor frame; drop.
            return
        if seq_id != st.sequence_id:
            # New message from same sender interleaved before the previous one
            # completed. Drop the stale buffer and ignore this stray frame —
            # the next frame-0 with the new seq will start fresh.
            self._buffers.pop(key, None)
            return
        if frame_counter != st.next_frame_counter:
            # Out of order. N2K does not guarantee retransmission, so the
            # message is unrecoverable; drop the buffer.
            self._buffers.pop(key, None)
            return

        st.received_bytes.extend(data[1:8])  # 7 useful bytes per continuation
        st.next_frame_counter += 1
        st.last_seen = now

        if len(st.received_bytes) >= st.expected_length:
            payload = bytes(st.received_bytes[: st.expected_length])
            self._buffers.pop(key, None)
            yield payload

    def _expire_stale(self, now: float) -> None:
        stale = [k for k, st in self._buffers.items() if now - st.last_seen > self._timeout_s]
        for k in stale:
            self._buffers.pop(k, None)


def load_fast_packet_pgns(pgns_json: dict[str, Any]) -> set[int]:
    """Extract the set of fast-packet PGN numbers from a canboat pgns.json blob.

    A PGN is treated as fast-packet if its entry has ``Type == "Fast"`` or if
    its declared length (``Length`` / ``MinLength``) is greater than 8 bytes.
    Canboat's bundled DB always exposes ``Type``; the length heuristic is a
    safety net for stripped-down forks.
    """
    result: set[int] = set()
    pgns = pgns_json.get("PGNs") or pgns_json.get("pgns") or []
    for p in pgns:
        pgn_raw = p.get("PGN") or p.get("pgn")
        if pgn_raw is None:
            continue
        try:
            pgn = int(pgn_raw)
        except (TypeError, ValueError):
            continue
        type_val = p.get("Type") or p.get("type") or ""
        if isinstance(type_val, str) and type_val.strip().lower() == "fast":
            result.add(pgn)
            continue
        length_val = p.get("Length") or p.get("MinLength") or p.get("length") or 0
        try:
            length = int(length_val)
        except (TypeError, ValueError):
            length = 0
        if length > 8:
            result.add(pgn)
    return result


__all__ = ["FastPacketReassembler", "load_fast_packet_pgns"]
