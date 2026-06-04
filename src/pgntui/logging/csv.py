"""Per-signal CSV logger with daily rotation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import IO


class CSVSignalLogger:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._handles: dict[tuple[str, str], IO[str]] = {}

    def _open(self, signal_id: str, day: str) -> IO[str]:
        key = (signal_id, day)
        fh = self._handles.get(key)
        if fh is None:
            path = self.base_dir / f"{signal_id}-{day}.csv"
            fh = path.open("a", encoding="utf-8")
            self._handles[key] = fh
        return fh

    def log(self, signal_id: str, timestamp: float, value: float | bool) -> None:
        dt = datetime.fromtimestamp(timestamp, tz=UTC)
        day = dt.strftime("%Y-%m-%d")
        # close any older-day handles for this signal
        stale = [k for k in self._handles if k[0] == signal_id and k[1] != day]
        for k in stale:
            self._handles.pop(k).close()
        fh = self._open(signal_id, day)
        fh.write(f"{dt.isoformat()},{value}\n")
        fh.flush()

    def close(self) -> None:
        for fh in self._handles.values():
            fh.close()
        self._handles.clear()


__all__ = ["CSVSignalLogger"]
