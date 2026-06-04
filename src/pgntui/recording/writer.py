"""Actisense .log writer."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from pgntui.drivers.base import Frame


class ActisenseLogWriter:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._fh: TextIO | None = None
        self.frame_count = 0
        self.bytes_written = 0

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # newline="" disables universal-newline translation so "\n" stays a single
        # byte on every platform (avoids CRLF pollution on Windows).
        self._fh = self.path.open("w", encoding="utf-8", newline="")

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def write(self, frame: Frame) -> None:
        assert self._fh is not None
        ts = datetime.fromtimestamp(frame.timestamp, tz=UTC).strftime("%Y-%m-%d-%H:%M:%S.%f")[:-3]
        fields = [
            ts,
            str(frame.priority),
            str(frame.pgn),
            str(frame.source_addr),
            str(frame.destination),
            str(len(frame.data)),
            *[f"{b:02x}" for b in frame.data],
        ]
        line = ",".join(fields) + "\n"
        self._fh.write(line)
        self.bytes_written += len(line.encode("utf-8"))
        self.frame_count += 1


__all__ = ["ActisenseLogWriter"]
