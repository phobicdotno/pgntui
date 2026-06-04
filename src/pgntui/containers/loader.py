"""Container JSON loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class ContainerLoadError(ValueError):
    """Raised when a container JSON document is invalid."""


@dataclass(frozen=True, slots=True)
class SignalPlacement:
    ref: str
    row: int
    col: int
    w: int


@dataclass(frozen=True, slots=True)
class Container:
    id: str
    title: str
    cols: int
    signals: list[SignalPlacement]


def load_container(path: Path, known_signal_ids: set[str]) -> Container:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ContainerLoadError(f"{path}: invalid JSON: {e}") from e
    try:
        cid = payload["id"]
        title = payload["title"]
    except KeyError as e:
        raise ContainerLoadError(f"{path}: missing key {e}") from e
    cols = int(payload.get("cols", 12))
    if cols <= 0:
        raise ContainerLoadError(f"{path}: cols must be positive")
    placements: list[SignalPlacement] = []
    # Track occupied cells to detect overlapping placements: (row, col) -> ref.
    occupied: dict[tuple[int, int], str] = {}
    for item in payload.get("signals", []):
        ref = item["ref"]
        if ref not in known_signal_ids:
            raise ContainerLoadError(f"{path}: unknown signal ref {ref!r}")
        row = int(item["row"])
        col = int(item["col"])
        w = int(item["w"])
        if row < 0 or col < 0 or w <= 0:
            raise ContainerLoadError(f"{path}: ref {ref!r} has invalid geometry")
        if col + w > cols:
            raise ContainerLoadError(f"{path}: ref {ref!r} overflows grid (cols={cols})")
        for c in range(col, col + w):
            cell = (row, c)
            if cell in occupied:
                raise ContainerLoadError(
                    f"{path}: placement {ref!r} overlaps existing "
                    f"{occupied[cell]!r} at row={row} col={c}"
                )
            occupied[cell] = ref
        placements.append(SignalPlacement(ref=ref, row=row, col=col, w=w))
    return Container(id=cid, title=title, cols=cols, signals=placements)


__all__ = ["Container", "ContainerLoadError", "SignalPlacement", "load_container"]
