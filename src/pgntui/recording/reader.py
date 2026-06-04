"""Actisense ASCII .log reader."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from pgntui.drivers.base import Frame


def parse_line(line: str) -> Frame | None:
    parts = line.strip().split(",")
    if len(parts) < 7:
        return None
    try:
        # Writer emits UTC timestamps via datetime.utcfromtimestamp; parse
        # them back as UTC so .timestamp() returns the original epoch value
        # rather than shifting by the local UTC offset.
        ts = datetime.strptime(parts[0], "%Y-%m-%d-%H:%M:%S.%f").replace(tzinfo=UTC).timestamp()
        priority = int(parts[1])
        pgn = int(parts[2])
        src = int(parts[3])
        destination = int(parts[4])
        length = int(parts[5])
        data = bytes(int(b, 16) for b in parts[6 : 6 + length])
    except (ValueError, IndexError):
        return None
    return Frame(
        timestamp=ts,
        source_addr=src,
        pgn=pgn,
        data=data,
        priority=priority,
        destination=destination,
    )


def read_log(path: Path) -> Iterator[Frame]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            frame = parse_line(line)
            if frame is not None:
                yield frame


__all__ = ["parse_line", "read_log"]
