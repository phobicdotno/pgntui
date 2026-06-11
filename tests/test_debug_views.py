"""Debug tab: toggle between the streaming trace and the aggregated per-PGN
monitor, and confirm repeated frames coalesce onto one row.
"""

from __future__ import annotations

import pytest
from textual.widgets import TabbedContent

from pgntui.app import DebugAggregate, DebugLog, PgntuiApp
from pgntui.decode.canboat import DecodedFrame
from pgntui.themes.loader import load_builtin


def _frame(pgn: int, src: int, value: int, ts: float = 1.0) -> DecodedFrame:
    return DecodedFrame(
        timestamp=ts, source_addr=src, pgn=pgn, name="Engine", fields={"rpm": value}
    )


@pytest.mark.asyncio
async def test_clear_debug_empties_buffer_log_and_table() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), pages=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        app._debug_buffer.push(_frame(127488, 0, 1000))
        app.query_one(TabbedContent).active = "debug"  # populate views from buffer
        await pilot.pause()
        assert len(app._debug_buffer.rows()) == 1
        app.action_clear_debug()
        await pilot.pause()
        assert app._debug_buffer.rows() == []  # buffer emptied
        assert app.query_one(DebugAggregate).row_count == 0  # table emptied


@pytest.mark.asyncio
async def test_debug_starts_on_stream_and_toggles() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), pages=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        log = app.query_one(DebugLog)
        table = app.query_one(DebugAggregate)
        # Stream is the default view; aggregate hidden.
        assert log.display is True
        assert table.display is False
        await pilot.press("g")
        await pilot.pause()
        assert log.display is False
        assert table.display is True  # aggregated view now shown
        await pilot.press("g")
        await pilot.pause()
        assert log.display is True
        assert table.display is False  # back to stream


@pytest.mark.asyncio
async def test_debug_log_is_capped() -> None:
    # The scrollback must be bounded — an unbounded RichLog grows without limit on
    # a live bus and eventually freezes when rendered.
    app = PgntuiApp(theme=load_builtin("dark"), pages=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(DebugLog).max_lines == 5000


@pytest.mark.asyncio
async def test_debug_views_fed_only_when_visible_and_repopulate_on_open() -> None:
    # While the Debug tab is hidden the per-frame UI hop is skipped (it floods the
    # event loop on a busy bus); the capped buffer still records, and the views are
    # rebuilt from it when Debug is opened.
    app = PgntuiApp(theme=load_builtin("dark"), page_titles=["Main"])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._debug_active is False  # Main is the active tab, Debug hidden
        # Frames accumulate in the capped buffer while Debug is hidden.
        for v in (1000, 1500, 50):
            app._debug_buffer.push(_frame(127488 if v != 50 else 127489, 0, v))
        assert app.query_one(DebugAggregate).row_count == 0  # views not fed yet
        # Opening Debug rebuilds the views from the buffer.
        app.query_one(TabbedContent).active = "debug"
        await pilot.pause()
        assert app._debug_active is True
        assert app.query_one(DebugAggregate).row_count == 2  # two distinct (pgn,src)


@pytest.mark.asyncio
async def test_aggregate_coalesces_repeated_pgns() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), pages=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one(DebugAggregate)
        table.push_decoded(_frame(127488, 0, 1000))
        table.push_decoded(_frame(127488, 0, 1500))  # same PGN+src -> updates row
        table.push_decoded(_frame(127489, 0, 50))  # different PGN -> new row
        await pilot.pause()
        assert table.row_count == 2
        # The repeated PGN row shows the latest value and a count of 2.
        assert str(table.get_cell("127488:0", "count")) == "2"
        assert "rpm=1500" in str(table.get_cell("127488:0", "fields"))


def _inst_frame(pgn: int, src: int, instance: int, rpm: int) -> DecodedFrame:
    return DecodedFrame(
        timestamp=1.0,
        source_addr=src,
        pgn=pgn,
        name="Engine",
        fields={"Instance": instance, "rpm": rpm},
    )


@pytest.mark.asyncio
async def test_aggregate_splits_rows_per_instance() -> None:
    # One PGN/source carrying several Instances gets one row per instance, not a
    # single coalesced row that jumps between engines.
    app = PgntuiApp(theme=load_builtin("dark"), pages=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one(DebugAggregate)
        table.push_decoded(_inst_frame(127489, 104, 0, 1778))
        table.push_decoded(_inst_frame(127489, 104, 1, 1519))
        table.push_decoded(_inst_frame(127489, 104, 0, 1800))  # updates instance 0
        await pilot.pause()
        assert table.row_count == 2  # one row per instance, not one merged row
        assert str(table.get_cell("127489:104:i0", "count")) == "2"
        assert str(table.get_cell("127489:104:i1", "count")) == "1"
        assert str(table.get_cell("127489:104:i0", "inst")) == "0"
        assert str(table.get_cell("127489:104:i1", "inst")) == "1"
