"""NGT-1 connection probe — the 'is it working?' self-test."""

from __future__ import annotations

from pgntui.drivers.actisense import ProbeResult, build_n2k_received, probe_ngt1


class FakeSerial:
    """Serial-like stub: yields queued chunks, then empty reads."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)
        self.closed = False

    def read(self, _n: int) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""

    def close(self) -> None:
        self.closed = True


def _factory(chunks: list[bytes]):
    holder: dict[str, FakeSerial] = {}

    def make(port: str, baud: int) -> FakeSerial:
        holder["serial"] = FakeSerial(chunks)
        return holder["serial"]

    make.holder = holder  # type: ignore[attr-defined]
    return make


def test_probe_reports_n2k_traffic() -> None:
    frame = build_n2k_received(prio=2, pgn=127488, dst=255, src=23, ts_ms=0, data=b"\x00" * 8)
    factory = _factory([frame, frame])
    res = probe_ngt1("COM4", baud=115200, duration=0.05, serial_factory=factory)
    assert isinstance(res, ProbeResult)
    assert res.ok is True
    assert res.n2k_messages == 2
    assert res.frames == 2
    assert 127488 in res.sample_pgns
    assert "Connected" in res.summary()
    assert factory.holder["serial"].closed is True  # type: ignore[attr-defined]


def test_probe_no_data_means_not_ok() -> None:
    res = probe_ngt1("COM4", duration=0.05, serial_factory=_factory([]))
    assert res.ok is False
    assert res.bytes_read == 0
    assert "no data" in res.summary().lower()


def test_probe_garbage_bytes_suggests_baud() -> None:
    res = probe_ngt1("COM4", duration=0.05, serial_factory=_factory([b"\xde\xad\xbe\xef" * 4]))
    assert res.ok is False
    assert res.bytes_read > 0
    assert res.frames == 0
    assert "speed" in res.summary().lower() or "baud" in res.summary().lower()


def test_probe_frames_but_no_n2k_flags_bus() -> None:
    # A valid BST frame with a non-N2K command (e.g. an NGT status 0xA0).
    from pgntui.drivers.actisense import frame_message

    status = frame_message(0xA0, b"\x01\x02\x03")
    res = probe_ngt1("COM4", duration=0.05, serial_factory=_factory([status]))
    assert res.frames == 1
    assert res.n2k_messages == 0
    assert "bus" in res.summary().lower()


def test_probe_open_failure_is_reported() -> None:
    def boom(port: str, baud: int):
        raise OSError("Access is denied")

    res = probe_ngt1("COM4", duration=0.05, serial_factory=boom)
    assert res.ok is False
    assert res.error is not None
    assert "Could not open" in res.summary()
    assert "Access is denied" in res.summary()
