import json
from pathlib import Path

import pytest

from pgntui.containers.loader import (
    Container,
    ContainerLoadError,
    SignalPlacement,
    load_container,
)


def _write_container(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "c.json"
    p.write_text(json.dumps(payload))
    return p


def test_load_container_ok(tmp_path: Path) -> None:
    p = _write_container(
        tmp_path,
        {
            "id": "engine_room",
            "title": "Engine Room",
            "cols": 12,
            "signals": [
                {"ref": "rpm_port", "row": 0, "col": 0, "w": 12},
                {"ref": "rpm_stbd", "row": 1, "col": 0, "w": 12},
            ],
        },
    )
    c = load_container(p, known_signal_ids={"rpm_port", "rpm_stbd"})
    assert isinstance(c, Container)
    assert c.cols == 12
    assert c.signals == [
        SignalPlacement(ref="rpm_port", row=0, col=0, w=12),
        SignalPlacement(ref="rpm_stbd", row=1, col=0, w=12),
    ]


def test_unknown_signal_ref_fails(tmp_path: Path) -> None:
    p = _write_container(
        tmp_path,
        {
            "id": "e",
            "title": "E",
            "cols": 12,
            "signals": [{"ref": "ghost", "row": 0, "col": 0, "w": 6}],
        },
    )
    with pytest.raises(ContainerLoadError):
        load_container(p, known_signal_ids=set())


def test_overflows_grid_fails(tmp_path: Path) -> None:
    p = _write_container(
        tmp_path,
        {
            "id": "e",
            "title": "E",
            "cols": 12,
            "signals": [{"ref": "a", "row": 0, "col": 8, "w": 8}],
        },
    )
    with pytest.raises(ContainerLoadError):
        load_container(p, known_signal_ids={"a"})


def test_negative_coords_fail(tmp_path: Path) -> None:
    p = _write_container(
        tmp_path,
        {
            "id": "e",
            "title": "E",
            "cols": 12,
            "signals": [{"ref": "a", "row": -1, "col": 0, "w": 4}],
        },
    )
    with pytest.raises(ContainerLoadError):
        load_container(p, known_signal_ids={"a"})


def test_overlapping_placements_rejected(tmp_path: Path) -> None:
    """Two placements covering the same cell must be rejected."""
    p = _write_container(
        tmp_path,
        {
            "id": "x",
            "title": "X",
            "cols": 12,
            "signals": [
                {"ref": "a", "row": 0, "col": 0, "w": 4},
                # Overlaps cols 2,3 with 'a'
                {"ref": "b", "row": 0, "col": 2, "w": 4},
            ],
        },
    )
    with pytest.raises(ContainerLoadError) as ei:
        load_container(p, known_signal_ids={"a", "b"})
    assert "overlap" in str(ei.value).lower()


def test_adjacent_placements_ok(tmp_path: Path) -> None:
    """Adjacent (non-overlapping) placements on the same row must succeed."""
    p = _write_container(
        tmp_path,
        {
            "id": "x",
            "title": "X",
            "cols": 12,
            "signals": [
                {"ref": "a", "row": 0, "col": 0, "w": 4},
                {"ref": "b", "row": 0, "col": 4, "w": 4},
            ],
        },
    )
    c = load_container(p, known_signal_ids={"a", "b"})
    assert len(c.signals) == 2


def test_same_columns_different_rows_ok(tmp_path: Path) -> None:
    """Same columns on different rows must not be flagged as overlap."""
    p = _write_container(
        tmp_path,
        {
            "id": "x",
            "title": "X",
            "cols": 12,
            "signals": [
                {"ref": "a", "row": 0, "col": 0, "w": 6},
                {"ref": "b", "row": 1, "col": 0, "w": 6},
            ],
        },
    )
    c = load_container(p, known_signal_ids={"a", "b"})
    assert len(c.signals) == 2
