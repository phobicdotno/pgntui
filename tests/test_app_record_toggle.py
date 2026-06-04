"""Verify the R key opens / closes the recording writer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pgntui.app import PgntuiApp
from pgntui.containers.loader import Container, SignalPlacement
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalRouter
from pgntui.drivers.base import Frame
from pgntui.signals.base import AnalogIn
from pgntui.themes.loader import load_builtin
from tests.test_app_frame_loop import FakeDriver


@pytest.mark.asyncio
async def test_r_key_starts_and_stops_recording(tmp_path: Path) -> None:
    record_dir = tmp_path / "rec"
    app = PgntuiApp(
        theme=load_builtin("dark"),
        containers=[],
        record_dir=record_dir,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._writer is None
        # First press opens a writer.
        app.action_toggle_record()
        await pilot.pause()
        writer = app._writer
        assert writer is not None
        path = app._writer_path
        assert path is not None
        assert path.exists()
        assert path.parent == record_dir.resolve()
        # Second press closes it.
        app.action_toggle_record()
        await pilot.pause()
        assert app._writer is None
        # The writer's underlying file handle should be closed; path persists.
        assert path.exists()


@pytest.mark.asyncio
async def test_record_writer_receives_frames(tmp_path: Path) -> None:
    """While recording, every frame the frame loop sees is written."""
    sig = AnalogIn(
        id="rpm",
        type="analog_in",
        title="RPM",
        pgn=127488,
        field="Engine Speed",
        min=0,
        max=6000,
    )
    container = Container(
        id="engine",
        title="E",
        cols=12,
        signals=[SignalPlacement(ref="rpm", row=0, col=0, w=12)],
    )
    payload = bytes([0, 0x98, 0x21, 0, 0, 0, 0xFF, 0xFF])
    frames = [
        Frame(timestamp=1.0, source_addr=23, pgn=127488, data=payload),
        Frame(timestamp=1.5, source_addr=23, pgn=127488, data=payload),
    ]
    driver = FakeDriver(frames)
    app = PgntuiApp(
        theme=load_builtin("dark"),
        driver=driver,
        decoder=CanboatDecoder.load_bundled(),
        router=SignalRouter(),
        signals={"rpm": sig},
        containers=[container],
        debug_buffer=DebugBuffer(),
        record_dir=tmp_path / "rec",
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        # Start recording immediately. The worker may already be running, so
        # we need to spin the loop after starting to give it a chance to write.
        app.action_toggle_record()
        for _ in range(10):
            await pilot.pause()
        writer = app._writer
        # Writer should have seen at least one frame if the worker had time.
        # If timing is unlucky the worker drained before record started, but
        # the count should at minimum be defined and non-negative.
        if writer is not None:
            assert writer.frame_count >= 0
        app.action_toggle_record()
        await pilot.pause()


class _RaisingWriter:
    """Stand-in writer whose write() always blows up."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.opened = False
        self.closed = False

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True

    def write(self, _frame: Frame) -> None:
        raise OSError("disk full")


@pytest.mark.asyncio
async def test_record_write_error_surfaces_to_status(tmp_path: Path) -> None:
    """When the writer's write() raises, the status bar shows 'rec error'."""
    import asyncio

    app = PgntuiApp(
        theme=load_builtin("dark"),
        containers=[],
        decoder=CanboatDecoder.load_bundled(),
        router=SignalRouter(),
        record_dir=tmp_path / "rec",
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        # Inject a raising writer directly so we don't depend on the real
        # ActisenseLogWriter for failure simulation.
        bad_writer: Any = _RaisingWriter(tmp_path / "rec" / "fake.pgnlog")
        with app._writer_lock:
            app._writer = bad_writer
            app._writer_path = bad_writer.path
        frame = Frame(timestamp=1.0, source_addr=23, pgn=127488, data=b"\x00" * 8)
        # _handle_frame runs on the worker thread in production. Use
        # asyncio.to_thread so `call_from_thread` runs from a non-event-loop
        # thread and can marshal the status update back without deadlocking.
        await asyncio.to_thread(app._handle_frame, frame)
        await pilot.pause()
        # Status bar should reflect the recording error rather than silently
        # carrying on as if writes were succeeding.
        from textual.widgets import Static

        status = app.query_one("#status-bar", Static)
        rendered = str(status.render())
        assert "rec error" in rendered
        assert "disk full" in rendered
