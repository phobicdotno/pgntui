"""Verify the app's background frame loop wires driver -> decoder -> widgets."""

from __future__ import annotations

import asyncio

import pytest

from pgntui.app import PgntuiApp
from pgntui.containers.loader import Container, SignalPlacement
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalKey, SignalRouter
from pgntui.drivers.base import Capability, Frame
from pgntui.signals.base import AnalogIn
from pgntui.themes.loader import load_builtin


class FakeDriver:
    """In-memory driver yielding a fixed list of frames then stopping."""

    name = "fake"
    capabilities = {Capability.READ}

    def __init__(self, frames: list[Frame]) -> None:
        self._frames = list(frames)
        self.opened = False
        self.closed = False
        self.written: list[Frame] = []

    def open(self, _config: dict[str, object]) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True

    def read_frames(self):  # type: ignore[no-untyped-def]
        yield from self._frames

    def write_frame(self, frame: Frame) -> None:
        self.written.append(frame)


def _engine_rpm_signal() -> AnalogIn:
    return AnalogIn(
        id="engine_rpm",
        type="analog_in",
        title="Engine RPM",
        pgn=127488,
        field="Engine Speed",
        source=23,
        min=0,
        max=6000,
    )


def _engine_container() -> Container:
    return Container(
        id="engine",
        title="Engine",
        cols=12,
        signals=[SignalPlacement(ref="engine_rpm", row=0, col=0, w=12)],
    )


def _engine_frame(value_lo: int, value_hi: int) -> Frame:
    # Engine Parameters Rapid Update: byte 0 = instance, bytes 1-2 = speed LE.
    return Frame(
        timestamp=1.0,
        source_addr=23,
        pgn=127488,
        data=bytes([0x00, value_lo, value_hi, 0x00, 0x00, 0x00, 0xFF, 0xFF]),
    )


@pytest.mark.asyncio
async def test_frame_loop_pushes_to_debug_buffer_and_updates_widgets() -> None:
    sig = _engine_rpm_signal()
    router = SignalRouter()
    router.bind("engine_rpm", SignalKey(pgn=sig.pgn, field=sig.field, source=23))
    debug = DebugBuffer()
    # Three frames at different speeds.
    frames = [
        _engine_frame(0x98, 0x21),  # 2150 rpm raw -> resolution 0.25 -> 2150
        _engine_frame(0xD0, 0x22),  # 2256 raw -> 2256
        _engine_frame(0x00, 0x23),  # 2304 raw -> 2304
    ]
    driver = FakeDriver(frames)
    app = PgntuiApp(
        theme=load_builtin("dark"),
        driver=driver,
        decoder=CanboatDecoder.load_bundled(),
        router=router,
        signals={"engine_rpm": sig},
        containers=[_engine_container()],
        debug_buffer=debug,
    )
    async with app.run_test() as pilot:
        # Let mount + worker thread + dispatched call_from_thread updates run.
        await pilot.pause()
        # The worker is in a thread; give the event loop a couple of beats so
        # any pending call_from_thread callbacks land before we assert.
        for _ in range(5):
            await asyncio.sleep(0.02)
        widget = app._widgets_by_signal["engine_rpm"][0]
        # Final value should be the third frame (without smoothing on this signal).
        assert widget.displayed_value > 0  # type: ignore[attr-defined]
        # All three decoded frames should be in the buffer.
        assert len(debug.rows()) == 3
        assert all(r.pgn == 127488 for r in debug.rows())
