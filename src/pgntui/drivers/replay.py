"""File-replay driver — feeds .pgnlog frames through the decode pipeline."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pgntui.drivers.base import Capability, Frame
from pgntui.recording.reader import read_log

_SPEED_MAP = {
    "0.25x": 0.25,
    "0.5x": 0.5,
    "1x": 1.0,
    "2x": 2.0,
    "5x": 5.0,
    "10x": 10.0,
    "max": float("inf"),
}


_PAUSE_POLL_INTERVAL = 0.05


class FileReplayDriver:
    name = "file-replay"
    capabilities = {Capability.READ, Capability.REPLAY}

    def __init__(self) -> None:
        self._path: Path | None = None
        self._speed: float = float("inf")
        self._paused: bool = False

    def open(self, config: dict[str, Any]) -> None:
        self._path = Path(config["path"])
        self._speed = _SPEED_MAP.get(config.get("speed", "max"), float("inf"))

    def close(self) -> None:
        self._path = None

    def set_paused(self, paused: bool) -> None:
        """Pause or resume frame emission.

        Sliding semantics: when resumed, the next frame fires after the normal
        inter-frame delay computed from the most recent emitted frame — we do
        NOT catch up the wall-clock time that elapsed while paused.
        """
        self._paused = paused

    def _interruptible_sleep(self, total: float) -> None:
        """Sleep for ``total`` seconds, but stop counting down while paused.

        Pause time is added on top of the remaining duration (sliding), so the
        scheduled inter-frame delay is honored in real time after resume rather
        than skipped.
        """
        remaining = total
        while remaining > 0:
            if self._paused:
                # Hold here without consuming the remaining delay.
                while self._paused:
                    time.sleep(_PAUSE_POLL_INTERVAL)
                # Resumed: keep the leftover delay intact and continue sleeping.
                continue
            step = remaining if remaining < _PAUSE_POLL_INTERVAL else _PAUSE_POLL_INTERVAL
            start = time.monotonic()
            time.sleep(step)
            remaining -= time.monotonic() - start

    def read_frames(self) -> Iterator[Frame]:
        if self._path is None:
            return
        prev_ts: float | None = None
        for frame in read_log(self._path):
            if self._speed != float("inf") and prev_ts is not None:
                dt = (frame.timestamp - prev_ts) / self._speed
                if dt > 0:
                    self._interruptible_sleep(dt)
            else:
                # No inter-frame delay (first frame or max speed): still honor
                # an active pause before yielding so users can pause from the
                # very start of replay.
                while self._paused:
                    time.sleep(_PAUSE_POLL_INTERVAL)
            prev_ts = frame.timestamp
            yield frame

    def write_frame(self, frame: Frame) -> None:
        raise NotImplementedError("replay driver is read-only")


__all__ = ["FileReplayDriver"]
