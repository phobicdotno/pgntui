from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from pgntui.pages.loader import (
    Container,
    Page,
    PageLoadError,
    SignalPlacement,
    load_page,
)


def _load(payload: dict, ids: set[str]) -> Page:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "p.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        return load_page(p, ids)


def test_parses_nested_page() -> None:
    page = _load(
        {
            "id": "engine",
            "title": "Engine",
            "instances": [{"id": 0, "label": "Stb"}],
            "containers": [
                {
                    "title": "Drive",
                    "cols": 12,
                    "signals": [
                        {"ref": "rpm", "row": 0, "col": 0, "w": 12},
                        {"ref": "boost", "row": 1, "col": 0, "w": 6},
                    ],
                }
            ],
        },
        {"rpm", "boost"},
    )
    assert page.id == "engine"
    assert page.instances[0].label == "Stb"
    assert len(page.containers) == 1
    c = page.containers[0]
    assert isinstance(c, Container)
    assert c.title == "Drive" and c.cols == 12
    assert c.signals[0] == SignalPlacement(ref="rpm", row=0, col=0, w=12)


def test_rejects_unknown_ref() -> None:
    with pytest.raises(PageLoadError):
        _load(
            {
                "id": "p",
                "title": "P",
                "containers": [
                    {
                        "title": "C",
                        "cols": 12,
                        "signals": [{"ref": "nope", "row": 0, "col": 0, "w": 6}],
                    }
                ],
            },
            set(),
        )


def test_rejects_overlap_within_container() -> None:
    with pytest.raises(PageLoadError):
        _load(
            {
                "id": "p",
                "title": "P",
                "containers": [
                    {
                        "title": "C",
                        "cols": 12,
                        "signals": [
                            {"ref": "a", "row": 0, "col": 0, "w": 6},
                            {"ref": "b", "row": 0, "col": 3, "w": 6},
                        ],
                    }
                ],
            },
            {"a", "b"},
        )


def test_rejects_overflow() -> None:
    with pytest.raises(PageLoadError):
        _load(
            {
                "id": "p",
                "title": "P",
                "containers": [
                    {
                        "title": "C",
                        "cols": 12,
                        "signals": [{"ref": "a", "row": 0, "col": 8, "w": 6}],
                    }
                ],
            },
            {"a"},
        )


def test_authored_page_requires_containers() -> None:
    with pytest.raises(PageLoadError):
        _load({"id": "p", "title": "P", "containers": []}, set())


def test_generated_page_must_be_empty() -> None:
    with pytest.raises(PageLoadError):
        _load(
            {
                "id": "auto",
                "title": "Auto",
                "generated": True,
                "containers": [{"title": "C", "cols": 12, "signals": []}],
            },
            set(),
        )
    ok = _load({"id": "auto", "title": "Auto", "generated": True, "containers": []}, set())
    assert ok.generated is True and ok.containers == ()
