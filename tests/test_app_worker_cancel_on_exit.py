"""Pressing Q cancels the frame_loop worker before the app exits.

Audit ref: docs/audits/2026-06-04-audit-A-concurrency.md finding A-1.
If the worker is left running while the event loop shuts down, its pending
``call_from_thread`` calls fire into a dead loop and surface as
``RuntimeError`` traces during quit.
"""

from __future__ import annotations

import threading
import time

import pytest
from textual.worker import WorkerState

from pgntui.app import PgntuiApp
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalKey, SignalRouter
from pgntui.drivers.base import Capability, Frame
from pgntui.pages.loader import Container, Page, SignalPlacement
from pgntui.signals.base import AnalogIn
from pgntui.themes.loader import load_builtin


class SlowDriver:
    """Driver whose ``read_frames`` blocks indefinitely until ``close`` flips
    a stop event — mirrors the shape of NGT1Driver/FileReplayDriver after the
    A-3/A-4 fixes. ``close()`` is what cooperatively unblocks the read loop.

    In production ``main()``'s ``finally`` calls ``driver.close()`` after
    ``app.run()`` returns; the test simulates that by closing the driver
    in a background thread as soon as ``action_force_quit`` fires.
    """

    name = "slow"
    capabilities = {Capability.READ}

    def __init__(self) -> None:
        self._stop = threading.Event()
        self.closed = False

    def open(self, _config: dict[str, object]) -> None:
        self._stop.clear()

    def close(self) -> None:
        self._stop.set()
        self.closed = True

    def read_frames(self):  # type: ignore[no-untyped-def]
        # Equivalent of NGT1Driver/FileReplayDriver cooperative stop loop.
        while not self._stop.is_set():
            time.sleep(0.01)
        return
        yield  # pragma: no cover — unreachable, keeps mypy happy

    def write_frame(self, frame: Frame) -> None:  # pragma: no cover — unused
        pass


def _engine_signal() -> AnalogIn:
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


def _engine_page() -> Page:
    return Page(
        id="engine",
        title="Engine",
        containers=(
            Container(
                title="Engine",
                cols=12,
                signals=(SignalPlacement(ref="engine_rpm", row=0, col=0, w=12),),
            ),
        ),
    )


def _build_app_with_slow_driver() -> tuple[PgntuiApp, SlowDriver]:
    sig = _engine_signal()
    router = SignalRouter()
    router.bind("engine_rpm", SignalKey(pgn=sig.pgn, field=sig.field, source=23))
    driver = SlowDriver()
    driver.open({})
    app = PgntuiApp(
        theme=load_builtin("dark"),
        driver=driver,
        decoder=CanboatDecoder.load_bundled(),
        router=router,
        signals={"engine_rpm": sig},
        pages=[_engine_page()],
        debug_buffer=DebugBuffer(),
    )
    return app, driver


@pytest.mark.asyncio
async def test_q_press_cancels_frame_loop_worker() -> None:
    """After Q the frame_loop worker must be CANCELLED, not RUNNING.

    Production lifecycle: ``main()`` calls ``driver.close()`` in its finally
    after ``app.run()`` returns. We simulate that ordering by closing the
    driver from a watchdog thread once the app starts shutting down — this
    lets the read loop unblock so ``run_test()`` can fully tear down.
    """
    app, driver = _build_app_with_slow_driver()

    # Watchdog: as soon as ``app.is_running`` flips False, close the driver
    # so the worker's read loop exits and the thread can join.
    started = threading.Event()

    def watchdog() -> None:
        # Wait until the app actually starts running before arming.
        for _ in range(200):
            if app.is_running:
                started.set()
                break
            time.sleep(0.05)
        for _ in range(200):  # ~10s budget after start
            if not app.is_running:
                driver.close()
                return
            time.sleep(0.05)
        driver.close()  # defensive — make sure we never leak the thread

    wd = threading.Thread(target=watchdog, name="driver-closer", daemon=True)
    wd.start()

    try:
        async with app.run_test() as pilot:
            # Wait until the worker appears (up to ~1s budget).
            frame_workers_before: list = []
            for _ in range(20):
                await pilot.pause()
                frame_workers_before = [
                    w for w in app.workers if w.group == "frame_loop" or w.name == "frame_loop"
                ]
                if frame_workers_before:
                    break
            assert frame_workers_before, (
                f"frame_loop worker never appeared; workers={list(app.workers)}"
            )

            await pilot.press("q")
            for _ in range(40):
                await pilot.pause()
                if not app.is_running:
                    break
    finally:
        wd.join(timeout=2)

    leftover_running = [
        w
        for w in app.workers
        if (w.group == "frame_loop" or w.name == "frame_loop") and w.state == WorkerState.RUNNING
    ]
    assert not leftover_running, f"frame_loop worker still running after exit: {leftover_running}"


@pytest.mark.asyncio
async def test_force_quit_action_cancels_worker_directly() -> None:
    """Direct ``action_force_quit`` (not via key press) also cancels workers."""
    app, driver = _build_app_with_slow_driver()

    def watchdog() -> None:
        for _ in range(200):
            if not app.is_running:
                driver.close()
                return
            time.sleep(0.05)
        driver.close()

    wd = threading.Thread(target=watchdog, name="driver-closer", daemon=True)
    wd.start()

    try:
        async with app.run_test() as pilot:
            for _ in range(5):
                await pilot.pause()
            app.action_force_quit()
            for _ in range(40):
                await pilot.pause()
                if not app.is_running:
                    break
    finally:
        wd.join(timeout=2)

    assert not app.is_running
    leftover_running = [w for w in app.workers if w.state == WorkerState.RUNNING]
    assert not leftover_running, f"worker still running after force_quit: {leftover_running}"
