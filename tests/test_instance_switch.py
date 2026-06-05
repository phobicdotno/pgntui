"""Instance-switchable containers: one source at a time, switched with [ / ]."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from pgntui.app import PgntuiApp
from pgntui.containers.loader import Container, InstanceOption, SignalPlacement, load_container
from pgntui.containers.screen import ContainerView, GroupRule
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder, DecodedFrame
from pgntui.decode.router import SignalKey, SignalRouter
from pgntui.drivers.base import Frame
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
                    "cols": 12,
                    "instances": [
                        {"id": 0, "label": "Engine Stb"},
                        {"id": 1, "label": "Engine Port"},
                    ],
                    "signals": [{"ref": "rpm", "row": 0, "col": 0, "w": 12}],
                }
            ),
            encoding="utf-8",
        )
        c = load_container(p, {"rpm"})
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


def _engine_container() -> Container:
    return Container(
        id="engine",
        title="Engine",
        cols=12,
        signals=[SignalPlacement(ref="rpm", row=0, col=0, w=12)],
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
        containers=[_engine_container()],
        decoder=CanboatDecoder.load_bundled(),
        router=router,
        debug_buffer=DebugBuffer(),
    )


@pytest.mark.asyncio
async def test_view_shows_instance_header_line() -> None:
    app = _app()
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        view = app.query_one(ContainerView)
        header = view._instance_header
        assert isinstance(header, GroupRule)
        plain = header.render().plain  # type: ignore[union-attr]
        assert "Engine Stb" in plain
        assert plain.startswith("├")
        assert view.active_instance_id == 0


@pytest.mark.asyncio
async def test_switching_instance_filters_frames() -> None:
    app = _app()
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        view = app.query_one(ContainerView)
        rpm = view.widgets["rpm"]
        assert isinstance(rpm, AnalogInWidget)
        loop = asyncio.get_running_loop()

        # Active instance 0: the inst-0 frame shows, the inst-1 frame is ignored.
        await loop.run_in_executor(None, app._handle_frame, _engine_frame(0, 1778))
        await loop.run_in_executor(None, app._handle_frame, _engine_frame(1, 1519))
        await pilot.pause()
        assert round(rpm.displayed_value) == 1778

        # Switch to instance 1 (Engine Port) and feed both again.
        app.action_next_instance()
        await pilot.pause()
        assert view.active_instance_id == 1
        assert "Engine Port" in view._instance_header.render().plain  # type: ignore[union-attr]
        await loop.run_in_executor(None, app._handle_frame, _engine_frame(0, 1778))
        await loop.run_in_executor(None, app._handle_frame, _engine_frame(1, 1519))
        await pilot.pause()
        assert round(rpm.displayed_value) == 1519

        # Wrap-around: [ from index 1 -> 0, ] cycles forward through 4 isn't
        # tested here (only two instances), but prev returns to Stb.
        app.action_prev_instance()
        await pilot.pause()
        assert view.active_instance_id == 0
