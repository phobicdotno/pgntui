from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from pgntui.pages.dashboard import DashboardView
from pgntui.pages.loader import Container, InstanceOption, Page, SignalPlacement
from pgntui.pages.view import GroupBox
from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget
from pgntui.themes.loader import load_builtin


def _sig(sid: str) -> AnalogIn:
    return AnalogIn(
        id=sid, type="analog_in", title=sid.upper(), pgn=127488, field="x", min=0, max=100
    )


def _signals() -> dict:
    return {s: _sig(s) for s in ("a", "b", "rpm")}


def _pages() -> list[Page]:
    nav = Page(
        id="nav",
        title="Nav",
        containers=(
            Container(title="Heading", cols=12, signals=(SignalPlacement("a", 0, 0, 12),)),
            Container(title="Speed", cols=12, signals=(SignalPlacement("b", 0, 0, 12),)),
        ),
    )
    eng = Page(
        id="engine",
        title="Engine",
        containers=(
            Container(title="Drive", cols=12, signals=(SignalPlacement("rpm", 0, 0, 12),)),
        ),
        instances=(InstanceOption(0, "Stb"), InstanceOption(1, "Port")),
    )
    return [nav, eng]


class _Host(App[None]):
    def compose(self) -> ComposeResult:
        yield DashboardView(
            pages=_pages(), signals=_signals(), write_enabled=False, theme=load_builtin("dark")
        )


@pytest.mark.asyncio
async def test_all_containers_render_as_boxes() -> None:
    async with _Host().run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        boxes = list(pilot.app.query(GroupBox))
        assert {str(b.border_title) for b in boxes} == {"Heading", "Speed", "Drive"}
        for b in boxes:
            assert b.region.height >= 3, "box not rendered with a border"


@pytest.mark.asyncio
async def test_responsive_columns_from_width() -> None:
    async with _Host().run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        grid = pilot.app.query_one("#dash-grid")
        # 120 // 48 = 2 columns (minus scrollbar still rounds to 2).
        assert grid.styles.grid_size_columns == 2


@pytest.mark.asyncio
async def test_instance_state_and_filtering() -> None:
    async with _Host().run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        dash = pilot.app.query_one(DashboardView)
        assert [o.label for o in dash.instances] == ["Stb", "Port"]
        assert dash.active_instance_id == 0
        assert "rpm" in dash.instanced_refs
        assert "a" not in dash.instanced_refs
        dash.set_active_instance(1)
        assert dash.active_instance_id == 1


@pytest.mark.asyncio
async def test_instance_switch_clears_only_instanced_widgets() -> None:
    async with _Host().run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        dash = pilot.app.query_one(DashboardView)
        rpm = dash.widgets["rpm"]
        nav_a = dash.widgets["a"]
        assert isinstance(rpm, AnalogInWidget) and isinstance(nav_a, AnalogInWidget)
        rpm.update_value(3000.0)
        nav_a.update_value(42.0)
        dash.set_active_instance(1)
        assert not rpm.has_data, "instanced widget should reset to diffuse"
        assert nav_a.has_data, "non-instanced widget must keep its reading"
