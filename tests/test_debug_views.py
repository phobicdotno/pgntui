"""Debug tab: toggle between the streaming trace and the aggregated per-PGN
monitor, and confirm repeated frames coalesce onto one row.
"""

from __future__ import annotations

import pytest

from pgntui.app import DebugAggregate, DebugLog, PgntuiApp
from pgntui.decode.canboat import DecodedFrame
from pgntui.themes.loader import load_builtin


def _frame(pgn: int, src: int, value: int, ts: float = 1.0) -> DecodedFrame:
    return DecodedFrame(
        timestamp=ts, source_addr=src, pgn=pgn, name="Engine", fields={"rpm": value}
    )


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
