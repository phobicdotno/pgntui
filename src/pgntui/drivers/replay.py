"""File-replay driver — feeds .pgnlog frames through the decode pipeline."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

from pgntui.drivers.base import Capability, Frame
from pgntui.recording.reader import read_log

_SPEED_MAP = {
    "0.25x": 0.25, "0.5x": 0.5, "1x": 1.0, "2x": 2.0,
    "5x": 5.0, "10x": 10.0, "max": float("inf"),
}


class FileReplayDriver:
    name = "file-replay"
    capabilities = {Capability.READ, Capability.REPLAY}

    def __init__(self) -> None:
        self._path: Path | None = None
        self._speed: float = float("inf")

    def open(self, config: dict) -> None:
        self._path = Path(config["path"])
        self._speed = _SPEED_MAP.get(config.get("speed", "max"), float("inf"))

    def close(self) -> None:
        self._path = None

    def read_frames(self) -> Iterator[Frame]:
        if self._path is None:
            return
        prev_ts: float | None = None
        for frame in read_log(self._path):
            if self._speed != float("inf") and prev_ts is not None:
                dt = (frame.timestamp - prev_ts) / self._speed
                if dt > 0:
                    time.sleep(dt)
            prev_ts = frame.timestamp
            yield frame

    def write_frame(self, frame: Frame) -> None:
        raise NotImplementedError("replay driver is read-only")


__all__ = ["FileReplayDriver"]
