"""Actisense NGT-1 driver (BST serial protocol).

Protocol verified against the canboat ``actisense-serial`` reference
(``actisense.h`` + ``actisense-serial.c``):

- Frames are delimited by ``DLE STX`` (start) and ``DLE ETX`` (end).
- Only ``DLE`` (0x10) is escaped inside a frame, by doubling. A bare STX/ETX
  in the body is a literal data byte — control bytes matter only after a DLE.
- Frame body = ``command, length, payload…, checksum`` where
  ``checksum = (256 - (command + length + sum(payload))) & 0xFF``.
- ``N2K_MSG_RECEIVED = 0x93`` carries a received N2K message (NGT-1 → PC);
  ``N2K_MSG_SEND = 0x94`` requests a transmit (PC → NGT-1).

Received payload layout (0x93):
``priority, PGN(3 LE), destination, source, timestamp(4 LE ms), length, data``.
Send payload layout (0x94):
``priority, PGN(3 LE), destination, length, data`` — no source/timestamp; the
device fills those in.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from pgntui.drivers.base import Capability, Frame

STX = 0x02
ETX = 0x03
DLE = 0x10
N2K_MSG_RECEIVED = 0x93
N2K_MSG_SEND = 0x94
# Commands sent TO the NGT-1 (vs N2K_MSG_* which carry bus traffic).
NGT_MSG_SEND = 0xA1

# "Receive all PGNs" startup command (canboat actisense-serial: NGT_STARTUP_SEQ).
# By default the NGT-1 forwards only network-management PGNs (heartbeats, address
# claims); this clears its PGN TX filter list so it emits EVERY received PGN —
# without it no sensor data (engine, GPS, …) reaches the host. canboat sends it
# on open and re-sends every 20s to keep the mode active, so we do the same.
_NGT_RECEIVE_ALL = bytes([0x11, 0x02, 0x00])
NGT_STARTUP_RESEND_SECONDS = 20.0


# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------


def _checksum(command: int, length: int, payload: bytes) -> int:
    return (256 - ((command + length + sum(payload)) & 0xFF)) & 0xFF


def frame_message(command: int, payload: bytes) -> bytes:
    """Wrap ``command`` + ``payload`` in a complete BST frame.

    Doubles every DLE in the body (command, length, payload, checksum) and
    wraps the result in ``DLE STX`` … ``DLE ETX``.
    """
    length = len(payload)
    body = bytearray([command, length])
    body += payload
    body.append(_checksum(command, length, payload))
    out = bytearray([DLE, STX])
    for b in body:
        if b == DLE:
            out.append(DLE)  # double the DLE
        out.append(b)
    out += bytes([DLE, ETX])
    return bytes(out)


def build_ngt_receive_all() -> bytes:
    """Framed NGT-1 command that puts the gateway into 'receive all PGNs' mode.

    Must be sent after opening the port (and re-sent periodically) or the NGT-1
    only forwards network-management PGNs and no sensor data arrives.
    """
    return frame_message(NGT_MSG_SEND, _NGT_RECEIVE_ALL)


def build_n2k_send(prio: int, pgn: int, dst: int, data: bytes) -> bytes:
    """Build a complete N2K_MSG_SEND (0x94) frame for transmission."""
    payload = bytearray()
    payload.append(prio & 0xFF)
    payload.append(pgn & 0xFF)
    payload.append((pgn >> 8) & 0xFF)
    payload.append((pgn >> 16) & 0xFF)
    payload.append(dst & 0xFF)
    payload.append(len(data))
    payload += data
    return frame_message(N2K_MSG_SEND, bytes(payload))


def build_n2k_received(prio: int, pgn: int, dst: int, src: int, ts_ms: int, data: bytes) -> bytes:
    """Build a complete N2K_MSG_RECEIVED (0x93) frame.

    Used to fabricate frames as the NGT-1 would emit them — handy for tests
    and replay tooling; the live driver only ever parses these.
    """
    payload = bytearray()
    payload.append(prio & 0xFF)
    payload.append(pgn & 0xFF)
    payload.append((pgn >> 8) & 0xFF)
    payload.append((pgn >> 16) & 0xFF)
    payload.append(dst & 0xFF)
    payload.append(src & 0xFF)
    payload += int(ts_ms).to_bytes(4, "little")
    payload.append(len(data))
    payload += data
    return frame_message(N2K_MSG_RECEIVED, bytes(payload))


def parse_n2k_received(payload: bytes) -> Frame | None:
    """Parse a 0x93 message payload into a :class:`Frame`.

    ``payload`` is the body between ``length`` and ``checksum`` — i.e. what
    :class:`MessageReassembler` yields. Returns ``None`` if too short.
    """
    if len(payload) < 11:
        return None
    priority = payload[0]
    pgn = payload[1] | (payload[2] << 8) | (payload[3] << 16)
    dst = payload[4]
    src = payload[5]
    ts_ms = int.from_bytes(payload[6:10], "little")
    data_len = payload[10]
    data = bytes(payload[11 : 11 + data_len])
    return Frame(
        timestamp=ts_ms / 1000.0,
        source_addr=src,
        pgn=pgn,
        data=data,
        priority=priority,
        destination=dst,
    )


class MessageReassembler:
    """Streaming BST unframer.

    Feed raw serial bytes via :meth:`push`; it returns a list of
    ``(command, payload)`` tuples for every complete, checksum-valid frame.
    Implements the canboat receive state machine: DLE toggles escape; after a
    DLE, STX starts a frame, ETX ends it, and DLE is a literal byte.
    """

    _IDLE = 0
    _IN_MSG = 1

    def __init__(self) -> None:
        self._state = self._IDLE
        self._escape = False
        self._buf = bytearray()

    def push(self, chunk: bytes) -> list[tuple[int, bytes]]:
        out: list[tuple[int, bytes]] = []
        for b in chunk:
            if self._escape:
                self._escape = False
                if b == STX:
                    self._state = self._IN_MSG
                    self._buf = bytearray()
                elif b == ETX:
                    if self._state == self._IN_MSG:
                        msg = self._finish()
                        if msg is not None:
                            out.append(msg)
                    self._state = self._IDLE
                    self._buf = bytearray()
                elif b == DLE:
                    if self._state == self._IN_MSG:
                        self._buf.append(DLE)
                else:
                    # DLE followed by anything else: framing error, resync.
                    self._state = self._IDLE
                    self._buf = bytearray()
                continue
            if b == DLE:
                self._escape = True
                continue
            if self._state == self._IN_MSG:
                self._buf.append(b)
        return out

    def _finish(self) -> tuple[int, bytes] | None:
        # buf = command, length, payload…, checksum
        if len(self._buf) < 3:
            return None
        command = self._buf[0]
        length = self._buf[1]
        if len(self._buf) < 2 + length + 1:
            return None
        payload = bytes(self._buf[2 : 2 + length])
        checksum = self._buf[2 + length]
        if _checksum(command, length, payload) != checksum:
            return None
        return command, payload


# ---------------------------------------------------------------------------
# Serial port discovery
# ---------------------------------------------------------------------------


def list_serial_ports() -> list[tuple[str, str]]:
    """Return ``(device, description)`` for every serial port, or ``[]``.

    Used by ``pgntui --list-ports`` so a user can find their NGT-1's COM/tty
    name without guessing.
    """
    try:
        from serial.tools import list_ports  # type: ignore[import-untyped]
    except Exception:  # pragma: no cover — pyserial missing
        return []
    return [(p.device, p.description or "") for p in list_ports.comports()]


# ---------------------------------------------------------------------------
# Connection probe — the "is it working?" self-test
# ---------------------------------------------------------------------------


@dataclass
class ProbeResult:
    """Outcome of :func:`probe_ngt1`."""

    ok: bool
    port: str
    baud: int
    bytes_read: int = 0
    frames: int = 0
    n2k_messages: int = 0
    sample_pgns: list[int] = field(default_factory=list)
    error: str | None = None

    def summary(self) -> str:
        """A human-readable verdict suitable for the UI or CLI."""
        if self.error is not None:
            return (
                f"Could not open {self.port}: {self.error}. "
                "Check the port name and that nothing else is using it."
            )
        if self.bytes_read == 0:
            return (
                f"{self.port} opened, but no data arrived. Check the NGT-1 is powered "
                "and the USB cable is connected."
            )
        if self.frames == 0:
            return (
                f"{self.port}: received {self.bytes_read} bytes but no valid NGT-1 frames "
                "— try a different speed (baud)."
            )
        if self.n2k_messages == 0:
            return (
                f"{self.port}: NGT-1 is responding ({self.frames} frames) but no NMEA 2000 "
                "bus traffic yet. Check the backbone connection and termination."
            )
        pgns = ", ".join(str(p) for p in self.sample_pgns)
        return (
            f"Connected on {self.port} @ {self.baud} baud — {self.n2k_messages} N2K messages "
            f"in {self.frames} frames. PGNs seen: {pgns}"
        )


def _open_serial(port: str, baud: int) -> Any:
    import serial  # type: ignore[import-untyped]

    return serial.Serial(port=port, baudrate=int(baud), timeout=0.2)


def probe_ngt1(
    port: str,
    baud: int = 115200,
    duration: float = 2.0,
    serial_factory: Callable[[str, int], Any] | None = None,
) -> ProbeResult:
    """Open ``port`` at ``baud``, read for ``duration`` seconds, and report.

    Counts valid BST frames and N2K messages so the caller can tell apart "port
    won't open", "no data", "wrong speed", "NGT-1 fine but no bus traffic", and
    "connected and receiving". ``serial_factory`` is injectable for testing.
    """
    factory = serial_factory or _open_serial
    try:
        ser = factory(port, baud)
    except Exception as e:
        return ProbeResult(ok=False, port=port, baud=baud, error=str(e))
    res = ProbeResult(ok=False, port=port, baud=baud)
    reassembler = MessageReassembler()
    try:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            chunk = ser.read(256)
            if not chunk:
                continue
            res.bytes_read += len(chunk)
            for command, payload in reassembler.push(chunk):
                res.frames += 1
                if command == N2K_MSG_RECEIVED:
                    res.n2k_messages += 1
                    frame = parse_n2k_received(payload)
                    if (
                        frame is not None
                        and frame.pgn not in res.sample_pgns
                        and len(res.sample_pgns) < 8
                    ):
                        res.sample_pgns.append(frame.pgn)
    finally:
        try:
            ser.close()
        except Exception:  # pragma: no cover — defensive
            pass
    res.ok = res.frames > 0
    return res


class NGT1Driver:
    name = "actisense-ngt1"
    capabilities = {Capability.READ, Capability.WRITE}

    def __init__(self) -> None:
        self._serial: Any = None
        # Cooperative stop: ``close()`` sets this so ``read_frames`` can break
        # out of its blocking loop on the next iteration without waiting for
        # the underlying serial port to raise.
        self._stop: threading.Event = threading.Event()
        self._reassembler = MessageReassembler()

    def open(self, config: dict[str, Any]) -> None:
        import serial

        self._stop.clear()
        self._reassembler = MessageReassembler()
        self._serial = serial.Serial(
            port=config["port"],
            baudrate=int(config.get("baud", 115200)),
            timeout=0.1,
        )
        # Tell the NGT-1 to forward every PGN, not just network-management ones.
        self._send_receive_all()

    def _send_receive_all(self) -> None:
        """Send the 'receive all PGNs' command, ignoring write errors."""
        if self._serial is None:
            return
        try:
            self._serial.write(build_ngt_receive_all())
        except Exception:  # pragma: no cover — defensive
            pass

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
        # Re-send the receive-all command periodically — the NGT-1 reverts to its
        # default (network-management only) if it stops hearing it (canboat does
        # the same on a 20s cadence).
        last_keepalive = time.monotonic()
        while True:
            if self._stop.is_set():
                return
            if time.monotonic() - last_keepalive > NGT_STARTUP_RESEND_SECONDS:
                self._send_receive_all()
                last_keepalive = time.monotonic()
            chunk = self._serial.read(256)
            if not chunk:
                continue
            for command, payload in self._reassembler.push(chunk):
                if command != N2K_MSG_RECEIVED:
                    continue  # ignore NGT status/ack messages
                frame = parse_n2k_received(payload)
                if frame is not None:
                    yield frame

    def write_frame(self, frame: Frame) -> None:
        assert self._serial is not None
        self._serial.write(
            build_n2k_send(
                prio=frame.priority,
                pgn=frame.pgn,
                dst=frame.destination,
                data=frame.data,
            )
        )


__all__ = [
    "DLE",
    "ETX",
    "N2K_MSG_RECEIVED",
    "N2K_MSG_SEND",
    "NGT_MSG_SEND",
    "STX",
    "MessageReassembler",
    "NGT1Driver",
    "ProbeResult",
    "build_n2k_received",
    "build_n2k_send",
    "build_ngt_receive_all",
    "frame_message",
    "list_serial_ports",
    "parse_n2k_received",
    "probe_ngt1",
]
