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
        view.set_columns(1)
        await pilot.pause()
        assert [w.region.y for w in ws] == [1, 2, 3, 4, 5, 6]
        assert len({w.region.x for w in ws}) == 1
        # [2] -> two equal columns: pairs share a row again.
        view.set_columns(2)
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


@pytest.mark.asyncio
async def test_bars_fill_and_right_ends_align() -> None:
    # Bars fill the row's remaining width, and every bar ends at the same column
    # (fixed value area) regardless of each value's length.
    async with _MultiColHost().run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        view = pilot.app.query_one(PageView)
        view.set_columns(1)  # one column, full width
        await pilot.pause()
        ws = list(pilot.app.query(AnalogInWidget))
        ws[0].update_value(5.0)  # short value
        ws[1].update_value(100.0)  # longer value
        await pilot.pause()
        inners = [w._bar_inner_width() for w in ws]
        assert all(n > 18 for n in inners)  # bars fill (wider than the old fixed 18)
        assert len(set(inners)) == 1  # equal length -> right ends (┤) align


@pytest.mark.asyncio
async def test_three_column_layout_on_wide_screen() -> None:
    # On a wide enough terminal the [3] option is offered and lays the six
    # signals out three-per-row (y = [1,1,1,2,2,2], three distinct columns).
    async with _MultiColHost().run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        view = pilot.app.query_one(PageView)
        box = pilot.app.query_one(GroupBox)
        # Hint carries both axes: signal columns then group columns (Shift+).
        assert str(box.border_subtitle) == "[1] [2] [3]  Shift+[1] [2] [3]"
        view.set_columns(3)
        await pilot.pause()
        ws = list(pilot.app.query(AnalogInWidget))
        assert [w.region.y for w in ws] == [1, 1, 1, 2, 2, 2]
        assert len({w.region.x for w in ws}) == 3  # three distinct columns


@pytest.mark.asyncio
async def test_three_column_hidden_and_noop_on_narrow_screen() -> None:
    # On a narrow terminal [3] is not offered and set_columns(3) is a no-op:
    # the authored two-column layout is left untouched.
    async with _MultiColHost().run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        view = pilot.app.query_one(PageView)
        box = pilot.app.query_one(GroupBox)
        # Narrow: signal [3] and group [3] both drop off the hint.
        assert str(box.border_subtitle) == "[1] [2]  Shift+[1] [2]"
        ws = list(pilot.app.query(AnalogInWidget))
        assert [w.region.y for w in ws] == [1, 1, 2, 2, 3, 3]
        view.set_columns(3)  # refused — screen too narrow for three columns
        await pilot.pause()
        assert [w.region.y for w in ws] == [1, 1, 2, 2, 3, 3]  # unchanged


class _MultiBoxHost(App[None]):
    """Three separate container boxes, so the Shift+1/2/3 group-column layout has
    something to arrange side by side."""

    def compose(self) -> ComposeResult:
        sigs = {
            f"s{i}": AnalogIn(
                id=f"s{i}", type="analog_in", title=f"S{i}", pgn=1, field="x", min=0, max=100
            )
            for i in range(6)
        }
        containers = tuple(
            Container(
                title=f"Box{b}",
                cols=12,
                signals=(
                    SignalPlacement(f"s{2 * b}", 0, 0, 6),
                    SignalPlacement(f"s{2 * b + 1}", 0, 6, 6),
                ),
            )
            for b in range(3)
        )
        page = Page(id="multi", title="Multi", containers=containers)
        yield PageView(page=page, signals=sigs, write_enabled=False, theme=load_builtin("dark"))


@pytest.mark.asyncio
async def test_group_columns_arrange_boxes_side_by_side() -> None:
    # Shift+1/2/3 lay the three container boxes out in 1/2/3 columns across the
    # page, and the signal density inside each box auto-shifts inversely.
    async with _MultiBoxHost().run_test(size=(130, 40)) as pilot:
        await pilot.pause()
        view = pilot.app.query_one(PageView)
        boxes = list(pilot.app.query(GroupBox))
        assert len(boxes) == 3
        # Default: one group column -> boxes stack (one column, three rows).
        assert len({b.region.x for b in boxes}) == 1
        assert len({b.region.y for b in boxes}) == 3
        # Shift+2 -> two group columns; signals inside auto-shift to 2 columns.
        view.set_group_columns(2)
        await pilot.pause()
        assert len({b.region.x for b in boxes}) == 2  # two side-by-side columns
        assert boxes[0].region.y == boxes[1].region.y  # first two share a row
        assert boxes[2].region.y > boxes[0].region.y  # third wraps below
        assert view._layout_cols == 2
        # Shift+3 -> three group columns; signals inside collapse to 1 column.
        view.set_group_columns(3)
        await pilot.pause()
        assert len({b.region.y for b in boxes}) == 1  # all three on one row
        assert len({b.region.x for b in boxes}) == 3
        assert view._layout_cols == 1
        # Shift+1 -> back to a single stacked column; signals back to 3-wide.
        view.set_group_columns(1)
        await pilot.pause()
        assert len({b.region.x for b in boxes}) == 1
        assert view._layout_cols == 3  # 1 group column -> 3 signal columns (wide screen)


@pytest.mark.asyncio
async def test_group_columns_gated_by_width() -> None:
    # Group columns need ~40 cols each: 2 cols need >=80, 3 need >=120.
    async with _MultiBoxHost().run_test(size=(90, 40)) as pilot:
        await pilot.pause()
        view = pilot.app.query_one(PageView)
        boxes = list(pilot.app.query(GroupBox))
        view.set_group_columns(3)  # refused at 90 cols (needs >=120)
        await pilot.pause()
        assert len({b.region.x for b in boxes}) == 1  # unchanged, still stacked
        view.set_group_columns(2)  # allowed at 90 cols (needs >=80)
        await pilot.pause()
        assert len({b.region.x for b in boxes}) == 2
