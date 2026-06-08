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
        captured["containers"] = [p.id for p in self._pages]
        captured["signals"] = sorted(self._signals.keys())
        captured["driver_type"] = type(self._n2k_driver).__name__

    with patch.object(PgntuiApp, "run", fake_run):
        rc = main(["--workspace", str(ws), "replay", str(fixture)])
    assert rc == 0
    assert captured["containers"] == ["engine", "nav"]
    assert "engine_rpm" in captured["signals"]
    assert captured["driver_type"] == "FileReplayDriver"


@pytest.mark.asyncio
async def test_replay_app_composes_one_content_tab(tmp_path: Path) -> None:
    """The composed app mounts a single content tab (Main) holding every source
    page as a section, plus Auto (driver present) and Debug."""
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
        assert "tab-content" in tab_ids
        assert "tab-auto" in tab_ids
        assert "debug" in tab_ids
        # No more one-tab-per-page; the pages live as sections in the content tab.
        assert "tab-engine" not in tab_ids
        assert "tab-nav" not in tab_ids
        page_titles = {page.title for page, _view in app._page_views}
        assert {"Nav", "Engine"} <= page_titles
    # Allow the background worker to wind down before closing the driver.
    await asyncio.sleep(0)
    drv.close()


@pytest.mark.asyncio
async def test_f_keys_arrange_auto_boxes(tmp_path: Path) -> None:
    """On the Auto tab F1/F2/F3 arrange the PGN boxes into 1/2/3 columns (the Auto
    page is one view of many boxes, not a section grid)."""
    from textual.widgets import TabbedContent

    ws = _make_workspace(tmp_path)
    cfg = Config(theme="dark", workspace=ws)
    drv = FileReplayDriver()
    drv.open({"path": str(FX / "e2e_session.pgnlog"), "speed": "max"})
    app = _build_app(cfg=cfg, workspace=ws, driver=drv)
    async with app.run_test(size=(150, 40)) as pilot:
        await pilot.pause()
        app.query_one(TabbedContent).active = "tab-auto"
        await pilot.pause()
        assert app._auto_view is not None
        await pilot.press("f2")
        await pilot.pause()
        assert app._auto_view._group_cols == 2
        await pilot.press("f1")
        await pilot.pause()
        assert app._auto_view._group_cols == 1
    await asyncio.sleep(0)
    drv.close()


@pytest.mark.asyncio
async def test_f_keys_set_page_columns(tmp_path: Path) -> None:
    """F1/F2/F3 lay the content sections out in 1/2/3 page-columns. Ctrl+digit is
    not delivered by legacy terminals, so the F-keys are the reliable binding."""
    from textual.widgets import TabbedContent

    ws = _make_workspace(tmp_path)
    cfg = Config(theme="dark", workspace=ws)
    app = _build_app(cfg=cfg, workspace=ws, driver=None)
    async with app.run_test(size=(150, 40)) as pilot:
        await pilot.pause()
        app.query_one(TabbedContent).active = "tab-content"
        await pilot.pause()
        assert app._page_cols == 1
        await pilot.press("f3")
        await pilot.pause()
        assert app._page_cols == 3
        await pilot.press("f2")
        await pilot.pause()
        assert app._page_cols == 2
        await pilot.press("f1")
        await pilot.pause()
        assert app._page_cols == 1
