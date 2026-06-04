from pathlib import Path

from pgntui.drivers.replay import FileReplayDriver
from pgntui.replay_mode import SPEED_LADDER, ReplaySession

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pgnlog"


def test_speed_cycle() -> None:
    s = ReplaySession(path=FIXTURE)
    start = s.speed
    assert start in SPEED_LADDER
    s.cycle_speed()
    assert s.speed != start


def test_writes_disabled() -> None:
    s = ReplaySession(path=FIXTURE)
    assert s.write_enabled is False


def test_iterates_through_file() -> None:
    s = ReplaySession(path=FIXTURE, speed="max")
    driver = s.driver
    assert isinstance(driver, FileReplayDriver)
    s.open()
    frames = list(s.iter_frames())
    s.close()
    assert len(frames) == 3


def test_pause_resume_state() -> None:
    s = ReplaySession(path=FIXTURE)
    assert not s.paused
    s.toggle_pause()
    assert s.paused
    s.toggle_pause()
    assert not s.paused
