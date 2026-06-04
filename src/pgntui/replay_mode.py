"""Replay session — wraps file-replay driver with transport state."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pgntui.drivers.base import Frame
from pgntui.drivers.replay import FileReplayDriver

SPEED_LADDER = ("0.25x", "0.5x", "1x", "2x", "5x", "10x", "max")


class ReplaySession:
    write_enabled = False

    def __init__(self, path: Path, speed: str = "1x") -> None:
        self.path = Path(path)
        if speed not in SPEED_LADDER:
            raise ValueError(f"unknown speed {speed!r}")
        self.speed = speed
        self.paused = False
        self.driver = FileReplayDriver()

    def cycle_speed(self) -> None:
        i = SPEED_LADDER.index(self.speed)
        self.speed = SPEED_LADDER[(i + 1) % len(SPEED_LADDER)]

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def open(self) -> None:
        self.driver.open({"path": str(self.path), "speed": self.speed})

    def close(self) -> None:
        self.driver.close()

    def iter_frames(self) -> Iterator[Frame]:
        yield from self.driver.read_frames()


__all__ = ["ReplaySession", "SPEED_LADDER"]
