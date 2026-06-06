from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from pgntui.pages.loader import Container, Page, SignalPlacement
from pgntui.pages.view import GroupBox, GroupRule, PageView
from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget
from pgntui.themes.loader import load_builtin


def _signals() -> dict:
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


def _page() -> Page:
    return Page(
        id="eng",
        title="Engine",
        containers=(
            Container(title="Drive", cols=12, signals=(SignalPlacement("rpm", 0, 0, 12),)),
        ),
    )


class _Host(App[None]):
    def compose(self) -> ComposeResult:
        yield PageView(
            page=_page(), signals=_signals(), write_enabled=False, theme=load_builtin("dark")
        )


def test_group_rule_text_spans_and_titles() -> None:
    rule = GroupRule("Engine", theme=load_builtin("dark"))
    rule.set_width(40)
    plain = rule.render().plain  # type: ignore[union-attr]
    assert "Engine" in plain
    assert plain.startswith("├")
    assert plain.rstrip().endswith("┤")


@pytest.mark.asyncio
async def test_pageview_renders_container_as_titled_box() -> None:
    async with _Host().run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        boxes = list(pilot.app.query(GroupBox))
        assert len(boxes) == 1
        assert str(boxes[0].border_title) == "Drive"
        w = pilot.app.query_one(AnalogInWidget)
        assert w.region.height == 1 and w.region.width > 0
        assert w in boxes[0].walk_children()
