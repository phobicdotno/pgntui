"""Driver Protocol, Capability enum, Frame dataclass."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class Capability(Enum):
    READ = "read"
    WRITE = "write"
    REPLAY = "replay"


@dataclass(frozen=True, slots=True)
class Frame:
    timestamp: float
    source_addr: int
    pgn: int
    data: bytes
    priority: int = 6
    """NMEA 2000 priority 0-7 (0 = highest, 7 = lowest). 6 = default info per spec."""
    destination: int = 255
    """N2K destination address. 255 = global broadcast."""


@runtime_checkable
class Driver(Protocol):
    name: str
    capabilities: set[Capability]

    def open(self, config: dict[str, Any]) -> None: ...
    def close(self) -> None: ...
    def read_frames(self) -> Iterator[Frame]: ...
    def write_frame(self, frame: Frame) -> None: ...
