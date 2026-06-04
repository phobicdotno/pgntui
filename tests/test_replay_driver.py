from pathlib import Path

from pgntui.drivers.base import Capability
from pgntui.drivers.replay import FileReplayDriver


FIXTURE = Path(__file__).parent / "fixtures" / "sample.pgnlog"


def test_capabilities() -> None:
    d = FileReplayDriver()
    assert Capability.READ in d.capabilities
    assert Capability.REPLAY in d.capabilities
    assert Capability.WRITE not in d.capabilities


def test_yields_frames_in_order() -> None:
    d = FileReplayDriver()
    d.open({"path": str(FIXTURE), "speed": "max"})
    frames = list(d.read_frames())
    d.close()
    assert len(frames) == 3
    assert frames[0].pgn == 127488
    assert frames[0].source_addr == 23
    assert frames[2].pgn == 130306
    assert frames[0].data[1] == 0x98


def test_speed_max_does_not_sleep() -> None:
    import time

    d = FileReplayDriver()
    d.open({"path": str(FIXTURE), "speed": "max"})
    t0 = time.monotonic()
    list(d.read_frames())
    d.close()
    assert time.monotonic() - t0 < 0.5
