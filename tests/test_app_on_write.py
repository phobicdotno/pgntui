"""Verify AnalogOut / DigitalOut widgets' on_write callbacks reach the driver."""

from __future__ import annotations

import pytest

from pgntui.app import PgntuiApp
from pgntui.containers.loader import Container, SignalPlacement
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalRouter
from pgntui.drivers.base import Capability, Frame
from pgntui.signals.base import AnalogOut, DigitalOut
from pgntui.signals.widgets import AnalogOutWidget, DigitalOutWidget
from pgntui.themes.loader import load_builtin


class CollectingDriver:
    name = "collect"
    capabilities = {Capability.READ, Capability.WRITE}

    def __init__(self) -> None:
        self.writes: list[Frame] = []

    def open(self, _config: dict[str, object]) -> None:
        pass

    def close(self) -> None:
        pass

    def read_frames(self):  # type: ignore[no-untyped-def]
        return iter(())  # no-op; we only care about writes here

    def write_frame(self, frame: Frame) -> None:
        self.writes.append(frame)


@pytest.mark.asyncio
async def test_analog_out_widget_triggers_driver_write_when_enabled() -> None:
    sig = AnalogOut(
        id="ap_heading",
        type="analog_out",
        title="AP Heading",
        pgn=65360,
        field="Heading",
        min=0,
        max=359,
        write_pgn=65360,
        write_field="Heading",
    )
    container = Container(
        id="ap",
        title="Autopilot",
        cols=12,
        signals=[SignalPlacement(ref=sig.id, row=0, col=0, w=12)],
    )
    driver = CollectingDriver()
    app = PgntuiApp(
        theme=load_builtin("dark"),
        driver=driver,
        decoder=CanboatDecoder.load_bundled(),
        router=SignalRouter(),
        signals={sig.id: sig},
        containers=[container],
        write_enabled=True,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        widget = app._widgets_by_signal[sig.id][0]
        assert isinstance(widget, AnalogOutWidget)
        # Callback should have been wired up at mount.
        assert widget.on_write is not None
        widget.submit_set(123.0)
        await pilot.pause()
        assert len(driver.writes) == 1
        assert driver.writes[0].pgn == 65360


@pytest.mark.asyncio
async def test_digital_out_widget_triggers_driver_write_when_enabled() -> None:
    sig = DigitalOut(
        id="anchor_light",
        type="digital_out",
        title="Anchor Light",
        pgn=127502,
        field="Indicator1",
        write_pgn=127502,
        write_field="Indicator1",
    )
    container = Container(
        id="lights",
        title="Lights",
        cols=12,
        signals=[SignalPlacement(ref=sig.id, row=0, col=0, w=12)],
    )
    driver = CollectingDriver()
    app = PgntuiApp(
        theme=load_builtin("dark"),
        driver=driver,
        decoder=CanboatDecoder.load_bundled(),
        router=SignalRouter(),
        signals={sig.id: sig},
        containers=[container],
        write_enabled=True,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        widget = app._widgets_by_signal[sig.id][0]
        assert isinstance(widget, DigitalOutWidget)
        assert widget.on_write is not None
        widget.toggle()
        await pilot.pause()
        assert len(driver.writes) == 1
        assert driver.writes[0].pgn == 127502
        assert driver.writes[0].data == b"\x01"


@pytest.mark.asyncio
async def test_write_disabled_does_not_call_driver() -> None:
    sig = DigitalOut(
        id="anchor_light",
        type="digital_out",
        title="Anchor Light",
        pgn=127502,
        field="Indicator1",
        write_pgn=127502,
        write_field="Indicator1",
    )
    container = Container(
        id="lights",
        title="Lights",
        cols=12,
        signals=[SignalPlacement(ref=sig.id, row=0, col=0, w=12)],
    )
    driver = CollectingDriver()
    app = PgntuiApp(
        theme=load_builtin("dark"),
        driver=driver,
        decoder=CanboatDecoder.load_bundled(),
        router=SignalRouter(),
        signals={sig.id: sig},
        containers=[container],
        write_enabled=False,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        widget = app._widgets_by_signal[sig.id][0]
        # With write_enabled=False, the widget refuses to even forward the call.
        assert isinstance(widget, DigitalOutWidget)
        widget.toggle()
        await pilot.pause()
        assert driver.writes == []
