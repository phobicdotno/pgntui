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


@runtime_checkable
class Driver(Protocol):
    name: str
    capabilities: set[Capability]

    def open(self, config: dict[str, Any]) -> None: ...
    def close(self) -> None: ...
    def read_frames(self) -> Iterator[Frame]: ...
    def write_frame(self, frame: Frame) -> None: ...
