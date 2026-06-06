from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from pgntui.decode.canboat import DecodedFrame
from pgntui.pages.auto import AutoPageBuilder
from pgntui.pages.loader import Page
from pgntui.pages.view import PageView
from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget, AutoTextWidget
from pgntui.themes.loader import load_builtin


class _Host(App[None]):
    def compose(self) -> ComposeResult:
        page = Page(id="auto", title="Auto", containers=(), generated=True)
        yield PageView(page=page, signals={}, write_enabled=False, theme=load_builtin("dark"))


def _frame(pgn: int, src: int, fields: dict, ts: float = 0.0) -> DecodedFrame:
    return DecodedFrame(timestamp=ts, source_addr=src, pgn=pgn, name="Test", fields=fields)


@pytest.mark.asyncio
async def test_auto_builds_container_per_pgn_source_and_updates() -> None:
    async with _Host().run_test(size=(90, 24)) as pilot:
        await pilot.pause()
        view = pilot.app.query_one(PageView)
        builder = AutoPageBuilder(view, theme=load_builtin("dark"))
        builder.ingest(_frame(127488, 0, {"Speed": 1000.0, "Label": "RUN"}, ts=0.0))
        await pilot.pause()
        assert builder.count == 1
        analogs = list(pilot.app.query(AnalogInWidget))
        texts = list(pilot.app.query(AutoTextWidget))
        assert len(analogs) == 1 and analogs[0].show_bar is False  # numeric, no bar
        assert len(texts) == 1  # string field -> text row
        assert texts[0]._text == "RUN"
        # Same (pgn, source): update in place, no new container.
        builder.ingest(_frame(127488, 0, {"Speed": 2000.0, "Label": "OFF"}, ts=1.0))
        await pilot.pause()
        assert builder.count == 1
        assert round(analogs[0].displayed_value) == 2000
        assert texts[0]._text == "OFF"
        # Different source -> a second container.
        builder.ingest(_frame(127488, 7, {"Speed": 50.0}, ts=2.0))
        await pilot.pause()
        assert builder.count == 2


@pytest.mark.asyncio
async def test_auto_respects_cap() -> None:
    async with _Host().run_test(size=(90, 24)) as pilot:
        await pilot.pause()
        view = pilot.app.query_one(PageView)
        builder = AutoPageBuilder(view, theme=load_builtin("dark"), max_containers=2)
        for src in range(5):
            builder.ingest(_frame(100, src, {"V": float(src)}, ts=float(src)))
        await pilot.pause()
        assert builder.count == 2
        assert builder.at_capacity


def test_analog_widget_hides_bar_when_show_bar_false() -> None:
    sig = AnalogIn(id="x", type="analog_in", title="X", pgn=1, field="f", unit="kn")
    w = AnalogInWidget(sig, show_bar=False)
    w.update_value(5.0)
    rendered = w.render_text()
    assert "├" not in rendered and "┤" not in rendered  # no bar glyphs
    assert "X" in rendered and "5" in rendered
