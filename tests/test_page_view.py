from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from pgntui.pages.loader import Container, Page, SignalPlacement
from pgntui.pages.view import GroupBox, GroupRule, PageView
from pgntui.signals.base import AnalogIn, AnalogOut, DigitalIn, DigitalOut
from pgntui.signals.widgets import (
    AnalogInWidget,
    AnalogOutWidget,
    DigitalInWidget,
    DigitalOutWidget,
)
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


@pytest.mark.asyncio
async def test_expanded_widget_grows_to_two_lines() -> None:
    async with _Host().run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        w = pilot.app.query_one(AnalogInWidget)
        assert w.region.height == 1  # collapsed stays tight
        w.update_value(1000.0, ts=0.0)
        w.update_value(5000.0, ts=1.0)
        w.toggle_sparkline()
        await pilot.pause()
        assert w.region.height == 2  # row grew to show the sparkline


class _DigitalHost(App[None]):
    def compose(self) -> ComposeResult:
        sig = DigitalIn(
            id="bilge", type="digital_in", title="Bilge", pgn=127501, field="Indicator1"
        )
        page = Page(
            id="p",
            title="P",
            containers=(
                Container(title="Pumps", cols=12, signals=(SignalPlacement("bilge", 0, 0, 12),)),
            ),
        )
        yield PageView(
            page=page, signals={"bilge": sig}, write_enabled=False, theme=load_builtin("dark")
        )


@pytest.mark.asyncio
async def test_expanded_digital_widget_grows_to_two_lines() -> None:
    async with _DigitalHost().run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        w = pilot.app.query_one(DigitalInWidget)
        assert w.region.height == 1  # collapsed stays tight
        w.update_value(True, ts=0.0)
        w.update_value(False, ts=1.0)
        w.toggle_sparkline()
        await pilot.pause()
        assert w.region.height == 2  # row grew to show the step-wave sparkline


class _MultiColHost(App[None]):
    def compose(self) -> ComposeResult:
        sigs = {
            f"s{i}": AnalogIn(
                id=f"s{i}", type="analog_in", title=f"S{i}", pgn=1, field="x", min=0, max=100
            )
            for i in range(6)
        }
        page = Page(
            id="nav",
            title="Nav",
            containers=(
                Container(
                    title="Heading",
                    cols=12,
                    signals=(
                        SignalPlacement("s0", 0, 0, 6),
                        SignalPlacement("s1", 0, 6, 6),
                        SignalPlacement("s2", 1, 0, 6),
                        SignalPlacement("s3", 1, 6, 6),
                        SignalPlacement("s4", 2, 0, 6),
                        SignalPlacement("s5", 2, 6, 6),
                    ),
                ),
            ),
        )
        yield PageView(page=page, signals=sigs, write_enabled=False, theme=load_builtin("dark"))


@pytest.mark.asyncio
async def test_multicolumn_rows_stay_tight_and_one_row_expands() -> None:
    # Regression guard: a 2-column grid must keep collapsed rows tight (an
    # ``auto`` row track once stretched them apart), and expanding one cell must
    # grow only that row.
    async with _MultiColHost().run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        ws = list(pilot.app.query(AnalogInWidget))
        # 3 rows of 2 cells, each one line, stacked 1 apart (no stretch).
        assert [w.region.y for w in ws] == [1, 1, 2, 2, 3, 3]
        assert all(w.region.height == 1 for w in ws)
        # Expand the middle row's first cell -> only that row grows to 2.
        ws[2].toggle_sparkline()
        await pilot.pause()
        assert ws[2].region.height == 2  # expanded row grew
        assert ws[0].region.height == 1  # row above unchanged
        assert ws[4].region.y == 4  # row below shifted down by exactly one line
        assert ws[4].region.height == 1


@pytest.mark.asyncio
async def test_column_toggle_switches_one_and_multi() -> None:
    async with _MultiColHost().run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        view = pilot.app.query_one(PageView)
        ws = list(pilot.app.query(AnalogInWidget))
        # Default 2-column layout: pairs share a row.
        assert [w.region.y for w in ws] == [1, 1, 2, 2, 3, 3]
        # [1] -> one column: each widget its own row, all in the same column.
        view.set_column_mode(True)
        await pilot.pause()
        assert [w.region.y for w in ws] == [1, 2, 3, 4, 5, 6]
        assert len({w.region.x for w in ws}) == 1
        # [2] -> back to the authored layout.
        view.set_column_mode(False)
        await pilot.pause()
        assert [w.region.y for w in ws] == [1, 1, 2, 2, 3, 3]


def test_output_rows_indented_to_align_with_inputs() -> None:
    # Outputs have no [+] toggle, so they get a 4-space indent to line up with
    # the [+]-prefixed input rows.
    ao = AnalogOutWidget(
        AnalogOut(
            id="o",
            type="analog_out",
            title="Target Heading",
            pgn=1,
            field="f",
            write_pgn=1,
            write_field="f",
        )
    )
    do = DigitalOutWidget(
        DigitalOut(
            id="d",
            type="digital_out",
            title="Anchor Light",
            pgn=1,
            field="f",
            write_pgn=1,
            write_field="f",
        )
    )
    assert ao.render_text().startswith("    ")
    assert do.render_text().startswith("    ")
