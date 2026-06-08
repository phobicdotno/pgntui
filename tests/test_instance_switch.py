"""Instance-switchable containers: one source at a time, switched with [ / ]."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from pgntui.app import PgntuiApp
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder, DecodedFrame
from pgntui.decode.router import SignalKey, SignalRouter
from pgntui.drivers.base import Frame
from pgntui.pages.loader import Container, InstanceOption, Page, SignalPlacement, load_page
from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget
from pgntui.themes.loader import load_builtin


def test_loader_parses_instances() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.json"
        p.write_text(
            json.dumps(
                {
                    "id": "engine",
                    "title": "Engine",
                    "instances": [
                        {"id": 0, "label": "Engine Stb"},
                        {"id": 1, "label": "Engine Port"},
                    ],
                    "containers": [
                        {
                            "title": "Engine",
                            "cols": 12,
                            "signals": [{"ref": "rpm", "row": 0, "col": 0, "w": 12}],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        c = load_page(p, {"rpm"})
    assert c.instances == (
        InstanceOption(id=0, label="Engine Stb"),
        InstanceOption(id=1, label="Engine Port"),
    )


def test_router_update_carries_instance() -> None:
    router = SignalRouter()
    router.bind("rpm", SignalKey(pgn=127488, field="Engine Speed"))
    decoded = DecodedFrame(
        timestamp=0.0,
        source_addr=0,
        pgn=127488,
        name="Engine",
        fields={"Instance": 1, "Engine Speed": 1519.0},
    )
    updates = list(router.route(decoded))
    assert len(updates) == 1
    assert updates[0].instance == 1


def _rpm_signal() -> AnalogIn:
    # No fixed instance + no smoothing, so the active-instance filter is the
    # only thing deciding what shows, and values are exact.
    return AnalogIn(
        id="rpm",
        type="analog_in",
        title="Engine RPM",
        pgn=127488,
        field="Engine Speed",
        min=0,
        max=6000,
        smoothing=0.0,
    )


def _engine_page() -> Page:
    return Page(
        id="engine",
        title="Engine",
        containers=(
            Container(
                title="Engine",
                cols=12,
                signals=(SignalPlacement(ref="rpm", row=0, col=0, w=12),),
            ),
        ),
        instances=(
            InstanceOption(id=0, label="Engine Stb"),
            InstanceOption(id=1, label="Engine Port"),
        ),
    )


def _engine_frame(instance: int, rpm: float) -> Frame:
    raw = round(rpm / 0.25)  # 127488 Engine Speed resolution is 0.25 rpm
    data = bytes([instance, raw & 0xFF, (raw >> 8) & 0xFF, 0xFF, 0xFF, 0x7F])
    return Frame(timestamp=0.0, source_addr=0, pgn=127488, data=data)


def _app() -> PgntuiApp:
    router = SignalRouter()
    router.bind("rpm", SignalKey(pgn=127488, field="Engine Speed"))
    return PgntuiApp(
        theme=load_builtin("dark"),
        signals={"rpm": _rpm_signal()},
        pages=[_engine_page()],
        decoder=CanboatDecoder.load_bundled(),
        router=router,
        debug_buffer=DebugBuffer(),
    )


@pytest.mark.asyncio
async def test_each_instance_is_its_own_fixed_section() -> None:
    # An instance-switchable page becomes one fixed, labelled section per
    # instance (no switcher) so they can all be shown at once.
    app = _app()
    async with app.run_test(size=(90, 30)) as pilot:
        await pilot.pause()
        views = [v for _p, v in app._page_views]
        assert len(views) == 2
        assert {v.fixed_instance for v in views} == {0, 1}
        assert {v.active_instance_id for v in views} == {0, 1}
        assert {v.section_title for v in views} == {"Engine Stb", "Engine Port"}
        # Each section is fixed, so none renders the click-to-switch InstanceBar.
        assert all(v._instance_header is None for v in views)


@pytest.mark.asyncio
async def test_instances_shown_simultaneously_without_jumping() -> None:
    # Each fixed section only accepts its own instance's frames, so feeding two
    # engines leaves each section showing its own value — no jumping.
    app = _app()
    async with app.run_test(size=(90, 30)) as pilot:
        await pilot.pause()
        by_inst = {v.fixed_instance: v for _p, v in app._page_views}
        rpm0 = by_inst[0].widgets["rpm"]
        rpm1 = by_inst[1].widgets["rpm"]
        assert isinstance(rpm0, AnalogInWidget)
        assert isinstance(rpm1, AnalogInWidget)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, app._handle_frame, _engine_frame(0, 1778))
        await loop.run_in_executor(None, app._handle_frame, _engine_frame(1, 1519))
        await pilot.pause()
        assert round(rpm0.displayed_value) == 1778
        assert round(rpm1.displayed_value) == 1519
