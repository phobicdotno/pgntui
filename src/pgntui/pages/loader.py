"""Page loader — parses the nested Page → Container → Signal JSON schema.

A page file declares a ``Page`` made of one or more ``Container`` boxes; each
container owns a grid of ``SignalPlacement`` entries positioned relative to that
container. A ``generated`` page declares no containers — it is filled at runtime
(the Auto page).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PageLoadError(ValueError):
    """Raised when a page JSON document is invalid."""


@dataclass(frozen=True, slots=True)
class SignalPlacement:
    ref: str
    row: int
    col: int
    w: int


@dataclass(frozen=True, slots=True)
class Container:
    """A titled box that owns a grid of signal placements (container-relative)."""

    title: str
    cols: int
    signals: tuple[SignalPlacement, ...]


@dataclass(frozen=True, slots=True)
class InstanceOption:
    """One selectable source for an instance-switchable page.

    ``id`` is the NMEA 2000 Instance value (e.g. 0/1/2/3 for Engine Stb / Port /
    generators); ``label`` is what the instance-switch header shows.
    """

    id: int
    label: str


@dataclass(frozen=True, slots=True)
class Page:
    id: str
    title: str
    containers: tuple[Container, ...] = ()
    # When non-empty the page shows one instance at a time, switchable with the
    # [ and ] keys. Its signals should omit a fixed ``instance``.
    instances: tuple[InstanceOption, ...] = ()
    # A generated page is populated at runtime (the Auto page) and declares no
    # containers in its JSON.
    generated: bool = False


def _parse_container(raw: dict[str, Any], known_signal_ids: set[str], source: str) -> Container:
    try:
        title = raw["title"]
    except KeyError as e:
        raise PageLoadError(f"{source}: container missing key {e}") from e
    cols = int(raw.get("cols", 12))
    if cols <= 0:
        raise PageLoadError(f"{source}: container {title!r} cols must be positive")
    placements: list[SignalPlacement] = []
    occupied: dict[tuple[int, int], str] = {}
    for item in raw.get("signals", []):
        ref = item["ref"]
        if ref not in known_signal_ids:
            raise PageLoadError(f"{source}: unknown signal ref {ref!r}")
        row, col, w = int(item["row"]), int(item["col"]), int(item["w"])
        if row < 0 or col < 0 or w <= 0:
            raise PageLoadError(f"{source}: ref {ref!r} has invalid geometry")
        if col + w > cols:
            raise PageLoadError(f"{source}: ref {ref!r} overflows container (cols={cols})")
        for c in range(col, col + w):
            cell = (row, c)
            if cell in occupied:
                raise PageLoadError(
                    f"{source}: {ref!r} overlaps {occupied[cell]!r} at row={row} col={c}"
                )
            occupied[cell] = ref
        placements.append(SignalPlacement(ref=ref, row=row, col=col, w=w))
    return Container(title=title, cols=cols, signals=tuple(placements))


def load_page(path: Path, known_signal_ids: set[str]) -> Page:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PageLoadError(f"{path}: invalid JSON: {e}") from e
    try:
        pid, title = payload["id"], payload["title"]
    except KeyError as e:
        raise PageLoadError(f"{path}: missing key {e}") from e
    generated = bool(payload.get("generated", False))
    raw_containers = payload.get("containers", [])
    if generated and raw_containers:
        raise PageLoadError(f"{path}: generated page must declare no containers")
    if not generated and not raw_containers:
        raise PageLoadError(f"{path}: page {pid!r} has no containers")
    containers = tuple(_parse_container(c, known_signal_ids, str(path)) for c in raw_containers)
    instances: list[InstanceOption] = []
    for item in payload.get("instances", []):
        try:
            instances.append(InstanceOption(id=int(item["id"]), label=str(item["label"])))
        except (KeyError, TypeError, ValueError) as e:
            raise PageLoadError(f"{path}: invalid instance entry {item!r}: {e}") from e
    return Page(
        id=pid,
        title=title,
        containers=containers,
        instances=tuple(instances),
        generated=generated,
    )


__all__ = [
    "Container",
    "InstanceOption",
    "Page",
    "PageLoadError",
    "SignalPlacement",
    "load_page",
]
