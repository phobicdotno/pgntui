"""Cover the replay subcommand wiring in pgntui.__main__."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from pgntui.__main__ import _build_app, main
from pgntui.app import PgntuiApp
from pgntui.config import Config
from pgntui.drivers.replay import FileReplayDriver

FX = Path(__file__).parent / "fixtures"


def _make_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "signals").mkdir(parents=True)
    (ws / "containers").mkdir(parents=True)
    # Reuse fixture signals + containers so we know they're decodable.
    for src in (FX / "e2e_signals").glob("*.json"):
        (ws / "signals" / src.name).write_text(src.read_text())
    for src in (FX / "e2e_containers").glob("*.json"):
        (ws / "containers" / src.name).write_text(src.read_text())
    return ws


def test_main_replay_missing_file_returns_2(tmp_path: Path) -> None:
    """Replay refuses to launch when the file doesn't exist."""
    ws = _make_workspace(tmp_path)
    rc = main(["--workspace", str(ws), "replay", str(tmp_path / "does-not-exist.pgnlog")])
    assert rc == 2


def test_main_replay_runs_app_with_containers(tmp_path: Path) -> None:
    """`pgntui replay` instantiates the app with the workspace's containers."""
    ws = _make_workspace(tmp_path)
    fixture = FX / "e2e_session.pgnlog"

    captured: dict[str, Any] = {}

    def fake_run(self: PgntuiApp, *_args: object, **_kwargs: object) -> None:
        captured["containers"] = [c.id for c in self._containers]
        captured["signals"] = sorted(self._signals.keys())
        captured["driver_type"] = type(self._n2k_driver).__name__

    with patch.object(PgntuiApp, "run", fake_run):
        rc = main(["--workspace", str(ws), "replay", str(fixture)])
    assert rc == 0
    assert captured["containers"] == ["engine", "nav"]
    assert "engine_rpm" in captured["signals"]
    assert captured["driver_type"] == "FileReplayDriver"


@pytest.mark.asyncio
async def test_replay_app_composes_tabpane_per_container(tmp_path: Path) -> None:
    """The composed app mounts one TabPane per container plus Debug."""
    ws = _make_workspace(tmp_path)
    cfg = Config(theme="dark", workspace=ws)
    drv = FileReplayDriver()
    drv.open({"path": str(FX / "e2e_session.pgnlog"), "speed": "max"})
    app = _build_app(cfg=cfg, workspace=ws, driver=drv)
    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import TabbedContent

        tabs = app.query_one(TabbedContent)
        tab_ids = sorted(tp.id or "" for tp in tabs.query("TabPane"))
        assert "tab-engine" in tab_ids
        assert "tab-nav" in tab_ids
        assert "debug" in tab_ids
    # Allow the background worker to wind down before closing the driver.
    await asyncio.sleep(0)
    drv.close()
