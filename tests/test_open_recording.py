"""The File > Open recording… browser and replay-a-recording flow."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from pgntui.app import OpenRecordingScreen, PgntuiApp, _RecordingTree
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalKey, SignalRouter
from pgntui.drivers.base import Frame
from pgntui.drivers.replay import FileReplayDriver
from pgntui.pages.loader import Container, Page, SignalPlacement
from pgntui.recording.writer import ActisenseLogWriter
from pgntui.signals.base import AnalogIn
from pgntui.themes.loader import load_builtin


def _frame(rpm: float, ts: float) -> Frame:
    raw = round(rpm / 0.25)  # 127488 Engine Speed resolution
    data = bytes([0xFF, raw & 0xFF, (raw >> 8) & 0xFF, 0xFF, 0xFF, 0x7F])
    return Frame(timestamp=ts, source_addr=0, pgn=127488, data=data)


def _write_recording(path: Path) -> None:
    writer = ActisenseLogWriter(path)
    writer.open()
    try:
        for i, rpm in enumerate([1000.0, 2000.0, 3000.0]):
            writer.write(_frame(rpm, 10.0 + i))
    finally:
        writer.close()


def _app(record_dir: Path | None = None) -> PgntuiApp:
    rpm = AnalogIn(
        id="rpm",
        type="analog_in",
        title="RPM",
        pgn=127488,
        field="Engine Speed",
        min=0,
        max=6000,
        smoothing=0.0,
    )
    page = Page(
        id="eng",
        title="Engine",
        containers=(
            Container(title="Drive", cols=12, signals=(SignalPlacement("rpm", 0, 0, 12),)),
        ),
    )
    router = SignalRouter()
    router.bind("rpm", SignalKey(pgn=127488, field="Engine Speed"))
    return PgntuiApp(
        theme=load_builtin("dark"),
        signals={"rpm": rpm},
        pages=[page],
        decoder=CanboatDecoder.load_bundled(),
        router=router,
        debug_buffer=DebugBuffer(),
        record_dir=record_dir,
    )


def test_recording_tree_keeps_only_dirs_and_pgnlog(tmp_path: Path) -> None:
    (tmp_path / "a.pgnlog").write_text("", encoding="utf-8")
    (tmp_path / "b.txt").write_text("", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / ".hidden").mkdir()
    tree = _RecordingTree(str(tmp_path))
    kept = {p.name for p in tree.filter_paths(sorted(tmp_path.iterdir()))}
    assert kept == {"a.pgnlog", "sub"}


@pytest.mark.asyncio
async def test_play_recording_swaps_in_a_replay_driver(tmp_path: Path) -> None:
    rec = tmp_path / "trip.pgnlog"
    _write_recording(rec)
    app = _app()
    async with app.run_test(size=(90, 24)) as pilot:
        await pilot.pause()
        ok, message = app.play_recording(rec, "max")
        assert ok, message
        assert isinstance(app._n2k_driver, FileReplayDriver)
        assert app._driver_options == {"path": str(rec), "speed": "max"}
        # The replay worker feeds frames through the pipeline; the shared clock
        # advances to the recording's last timestamp.
        loop = asyncio.get_running_loop()
        for _ in range(50):
            await pilot.pause()
            if app._clock >= 12.0:
                break
        assert app._clock == 12.0
        assert loop is asyncio.get_running_loop()


@pytest.mark.asyncio
async def test_play_recording_rejects_a_missing_file(tmp_path: Path) -> None:
    app = _app()
    async with app.run_test(size=(90, 24)) as pilot:
        await pilot.pause()
        ok, message = app.play_recording(tmp_path / "nope.pgnlog", "1x")
        assert not ok
        assert "Not a file" in message


@pytest.mark.asyncio
async def test_open_recording_action_pushes_the_browser(tmp_path: Path) -> None:
    app = _app(record_dir=tmp_path)
    async with app.run_test(size=(90, 24)) as pilot:
        await pilot.pause()
        app.action_open_recording()
        await pilot.pause()
        assert isinstance(app.screen, OpenRecordingScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, OpenRecordingScreen)
