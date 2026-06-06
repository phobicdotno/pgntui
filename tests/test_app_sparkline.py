from __future__ import annotations

import asyncio

import pytest

from pgntui.app import PgntuiApp
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalKey, SignalRouter
from pgntui.drivers.base import Frame
from pgntui.pages.loader import Container, Page, SignalPlacement
from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget
from pgntui.themes.loader import load_builtin


def _rpm() -> AnalogIn:
    return AnalogIn(id="rpm", type="analog_in", title="RPM", pgn=127488,
                    field="Engine Speed", min=0, max=6000, smoothing=0.0)


def _page() -> Page:
    return Page(id="eng", title="Engine",
                containers=(Container(title="Drive", cols=12,
                            signals=(SignalPlacement("rpm", 0, 0, 12),)),))


def _app() -> PgntuiApp:
    router = SignalRouter()
    router.bind("rpm", SignalKey(pgn=127488, field="Engine Speed"))
    return PgntuiApp(theme=load_builtin("dark"), signals={"rpm": _rpm()},
                     pages=[_page()], decoder=CanboatDecoder.load_bundled(),
                     router=router, debug_buffer=DebugBuffer())


def _frame(rpm: float, ts: float) -> Frame:
    raw = round(rpm / 0.25)  # 127488 Engine Speed resolution
    data = bytes([0xFF, raw & 0xFF, (raw >> 8) & 0xFF, 0xFF, 0xFF, 0x7F])
    return Frame(timestamp=ts, source_addr=0, pgn=127488, data=data)


@pytest.mark.asyncio
async def test_frame_timestamp_populates_history_and_clock() -> None:
    app = _app()
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        w = app.query_one(AnalogInWidget)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, app._handle_frame, _frame(1000.0, 10.0))
        await loop.run_in_executor(None, app._handle_frame, _frame(5000.0, 11.0))
        await pilot.pause()
        assert app._clock == 11.0
        assert w.sparkline_str(2) == "▁█"
