"""File-replay driver — feeds .pgnlog frames through the decode pipeline."""

from __future__ import annotations

import threading
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
        # Cooperative stop. ``close()`` sets this so any in-flight
        # ``read_frames`` generator on another thread exits at the next
        # iteration and ``_interruptible_sleep`` returns early. The underlying
        # file handle is opened inside ``read_log`` via a ``with`` block, so
        # exiting the generator releases the handle deterministically.
        self._stop: threading.Event = threading.Event()

    def open(self, config: dict[str, Any]) -> None:
        self._stop.clear()
        self._path = Path(config["path"])
        self._speed = _SPEED_MAP.get(config.get("speed", "max"), float("inf"))

    def close(self) -> None:
        self._stop.set()
        # Resuming a paused driver here makes the read loop notice ``_stop``
        # on the next polling tick rather than holding the pause forever.
        self._paused = False
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
        than skipped. If ``close()`` sets ``_stop`` mid-sleep, returns early.
        """
        remaining = total
        while remaining > 0:
            if self._stop.is_set():
                return
            if self._paused:
                # Hold here without consuming the remaining delay.
                while self._paused and not self._stop.is_set():
                    time.sleep(_PAUSE_POLL_INTERVAL)
                if self._stop.is_set():
                    return
                # Resumed: keep the leftover delay intact and continue sleeping.
                continue
            step = remaining if remaining < _PAUSE_POLL_INTERVAL else _PAUSE_POLL_INTERVAL
            start = time.monotonic()
            time.sleep(step)
            remaining -= time.monotonic() - start

    def read_frames(self) -> Iterator[Frame]:
        # Snapshot the path under the (effectively GIL-atomic) attribute read
        # so a concurrent ``close()`` nulling ``_path`` doesn't break the
        # already-open ``with`` block inside ``read_log``.
        path = self._path
        if path is None:
            return
        prev_ts: float | None = None
        for frame in read_log(path):
            if self._stop.is_set():
                return
            if self._speed != float("inf") and prev_ts is not None:
                dt = (frame.timestamp - prev_ts) / self._speed
                if dt > 0:
                    self._interruptible_sleep(dt)
            else:
                # No inter-frame delay (first frame or max speed): still honor
                # an active pause before yielding so users can pause from the
                # very start of replay. ``_stop`` breaks the wait out.
                while self._paused and not self._stop.is_set():
                    time.sleep(_PAUSE_POLL_INTERVAL)
            if self._stop.is_set():
                return
            prev_ts = frame.timestamp
            yield frame

    def write_frame(self, frame: Frame) -> None:
        raise NotImplementedError("replay driver is read-only")


__all__ = ["FileReplayDriver"]
