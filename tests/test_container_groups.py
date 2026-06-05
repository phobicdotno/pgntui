"""Container group headers and one-line rows.

Containers may declare ``groups`` — full-width separator rules rendered as
``├── Title ──────┤`` between signal rows. Signal rows are one line tall so
dense pages (engine status, binary) fit on screen.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from pgntui.app import PgntuiApp
from pgntui.containers.loader import Container, ContainerLoadError, GroupHeader, load_container
from pgntui.containers.screen import GroupRule
from pgntui.debug.tab import DebugBuffer
from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget
from pgntui.themes.loader import load_builtin


def _load(payload: dict, ids: set[str]) -> Container:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        return load_container(p, ids)


def test_loader_parses_groups() -> None:
    c = _load(
        {
            "id": "c",
            "title": "C",
            "cols": 12,
            "groups": [{"title": "Engine", "row": 0}, {"title": "Status", "row": 2}],
            "signals": [{"ref": "a", "row": 1, "col": 0, "w": 6}],
        },
        {"a"},
    )
    assert c.groups == (
        GroupHeader(title="Engine", row=0),
        GroupHeader(title="Status", row=2),
    )


def test_loader_rejects_group_row_collision_with_signal() -> None:
    with pytest.raises(ContainerLoadError):
        _load(
            {
                "id": "c",
                "title": "C",
                "cols": 12,
                "groups": [{"title": "Engine", "row": 0}],
                "signals": [{"ref": "a", "row": 0, "col": 0, "w": 6}],
            },
            {"a"},
        )


def test_loader_defaults_no_groups() -> None:
    c = _load(
        {
            "id": "c",
            "title": "C",
            "cols": 12,
            "signals": [{"ref": "a", "row": 0, "col": 0, "w": 6}],
        },
        {"a"},
    )
    assert c.groups == ()


def test_group_rule_text_spans_and_titles() -> None:
    rule = GroupRule("Engine", theme=load_builtin("dark"))
    rule.set_width(40)
    plain = rule.render().plain  # type: ignore[union-attr]
    assert "Engine" in plain
    assert plain.startswith("├")
    assert plain.rstrip().endswith("┤")


def _sig() -> dict:
    return {
        "rpm": AnalogIn(
            id="rpm",
            type="analog_in",
            title="RPM",
            pgn=127488,
            field="Engine Speed",
            min=0,
            max=6000,
        )
    }


@pytest.mark.asyncio
async def test_rows_are_single_line_and_group_renders() -> None:
    container = _load(
        {
            "id": "eng",
            "title": "Engine",
            "cols": 12,
            "groups": [{"title": "Engine", "row": 0}],
            "signals": [{"ref": "rpm", "row": 1, "col": 0, "w": 12}],
        },
        {"rpm"},
    )
    app = PgntuiApp(
        theme=load_builtin("dark"),
        signals=_sig(),
        containers=[container],
        debug_buffer=DebugBuffer(),
    )
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        w = app.query_one(AnalogInWidget)
        assert w.region.height == 1, "analog row should be one line tall"
        assert len(list(app.query(GroupRule))) == 1
