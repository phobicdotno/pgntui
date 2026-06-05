"""In-app Connection menu: port/speed selects, Test, Save, Connect."""

from __future__ import annotations

from pathlib import Path

import pytest

from pgntui.app import ConnectionScreen, PgntuiApp
from pgntui.config import load_config
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalRouter
from pgntui.drivers.actisense import ProbeResult
from pgntui.drivers.base import Frame
from pgntui.themes.loader import load_builtin

PORTS = [("COM4", "USB Serial Port"), ("COM7", "Actisense NGT-1")]


def _app(**kw) -> PgntuiApp:  # type: ignore[no-untyped-def]
    return PgntuiApp(theme=load_builtin("dark"), containers=[], debug_buffer=DebugBuffer(), **kw)


@pytest.mark.asyncio
async def test_connection_opens_via_key_and_lists_ports(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("pgntui.drivers.actisense.list_serial_ports", lambda: PORTS)
    app = _app(driver_options={"port": "COM7", "baud": 115200})
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        assert isinstance(app.screen, ConnectionScreen)
        from textual.widgets import Select

        port_select = app.screen.query_one("#port-select", Select)
        # Current port is pre-selected from driver_options.
        assert port_select.value == "COM7"


@pytest.mark.asyncio
async def test_connection_opens_via_button(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("pgntui.drivers.actisense.list_serial_ports", lambda: PORTS)
    app = _app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#connection-button")
        await pilot.pause()
        assert isinstance(app.screen, ConnectionScreen)


@pytest.mark.asyncio
async def test_test_button_runs_probe_and_shows_summary(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("pgntui.drivers.actisense.list_serial_ports", lambda: PORTS)
    monkeypatch.setattr(
        "pgntui.drivers.actisense.probe_ngt1",
        lambda port, baud=115200, duration=2.0, serial_factory=None: ProbeResult(
            ok=True,
            port=port,
            baud=baud,
            bytes_read=200,
            frames=4,
            n2k_messages=4,
            sample_pgns=[127488],
        ),
    )
    app = _app(driver_options={"port": "COM7", "baud": 115200})
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        await pilot.click("#conn-test")
        await app.workers.wait_for_complete()
        await pilot.pause()
        from textual.widgets import Static

        result = str(app.screen.query_one("#conn-result", Static).render())
        assert "Connected" in result


@pytest.mark.asyncio
async def test_save_button_writes_config(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("pgntui.drivers.actisense.list_serial_ports", lambda: PORTS)
    app = _app(workspace=tmp_path, driver_options={"port": "COM7", "baud": 115200})
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        await pilot.click("#conn-save")
        await pilot.pause()
        cfg = load_config(tmp_path / "config.toml")
        assert cfg.driver_name == "actisense-ngt1"
        assert cfg.driver_options["port"] == "COM7"
        assert cfg.driver_options["baud"] == 115200


class _FakeDriver:
    name = "actisense-ngt1"

    def __init__(self) -> None:
        self.opened: dict | None = None

    def open(self, options: dict) -> None:
        self.opened = options

    def read_frames(self):  # type: ignore[no-untyped-def]
        return iter(())  # no frames; loop ends immediately

    def write_frame(self, frame: Frame) -> None:  # pragma: no cover
        pass

    def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_connect_ngt1_wires_driver(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fake = _FakeDriver()
    monkeypatch.setattr("pgntui.drivers.actisense.NGT1Driver", lambda: fake)
    app = PgntuiApp(
        theme=load_builtin("dark"),
        containers=[],
        debug_buffer=DebugBuffer(),
        decoder=CanboatDecoder.load_bundled(),
        router=SignalRouter(),
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        ok, message = app.connect_ngt1("COM7", 115200)
        assert ok is True
        assert "Connected" in message
        assert app._n2k_driver is fake
        assert fake.opened == {"port": "COM7", "baud": 115200}
        # A second attempt refuses while a driver is live.
        ok2, message2 = app.connect_ngt1("COM4", 115200)
        assert ok2 is False
        assert "already connected" in message2.lower()
