"""Cover the replay subcommand wiring in pgntui.__main__."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from pgntui.__main__ import _build_app, main
from pgntui.app import PgntuiApp
from pgntui.config import Config, load_config
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
async def test_quit_closes_driver_and_releases_port(tmp_path: Path) -> None:
    """Quitting must close the driver — set its cooperative stop and release the
    serial port / file handle — so exit is prompt and the port is freed. (The bug:
    force_quit only cancelled the worker, which never stops the read loop.)"""
    ws = _make_workspace(tmp_path)
    cfg = Config(theme="dark", workspace=ws)
    drv = FileReplayDriver()
    drv.open({"path": str(FX / "e2e_session.pgnlog"), "speed": "max"})
    app = _build_app(cfg=cfg, workspace=ws, driver=drv)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not drv._stop.is_set()  # running
        app.action_force_quit()
        await pilot.pause()
        # close() ran: stop is set (read loop will return) and the path released.
        assert drv._stop.is_set()
        assert drv._path is None
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_saved_layout_restored_on_launch(tmp_path: Path) -> None:
    """A layout chosen with [1/2/3], Shift+1/2/3 or F1/F2/F3 is persisted and
    re-applied on the next launch."""
    from textual.widgets import TabbedContent

    ws = _make_workspace(tmp_path)
    # First launch: choose 2 signal columns and 3 page columns, which persists.
    cfg = load_config(ws / "config.toml")
    app = _build_app(cfg=cfg, workspace=ws, driver=None)
    async with app.run_test(size=(150, 40)) as pilot:
        await pilot.pause()
        app.query_one(TabbedContent).active = "tab-content"
        await pilot.pause()
        await pilot.press("2")  # signal columns
        await pilot.press("f3")  # page columns
        await pilot.pause()
        assert app._saved_signal_cols == 2
        assert app._saved_page_cols == 3

    # Second launch from the same workspace: the layout is restored from config.
    cfg2 = load_config(ws / "config.toml")
    assert cfg2.layout_columns == 2
    assert cfg2.layout_pages == 3
    app2 = _build_app(cfg=cfg2, workspace=ws, driver=None)
    async with app2.run_test(size=(150, 40)) as pilot:
        await pilot.pause()
        assert app2._saved_signal_cols == 2
        assert app2._page_cols == 3
        # Every content section was laid out in 2 signal columns on mount.
        for _page, view in app2._page_views:
            assert view._layout_cols == 2


@pytest.mark.asyncio
async def test_auto_fed_only_when_visible_and_repopulates_on_open(tmp_path: Path) -> None:
    """Auto isn't built/updated while hidden (no per-frame UI work for a tab nobody
    is viewing); it is rebuilt from the capped buffer when opened."""
    from textual.widgets import TabbedContent

    from pgntui.decode.canboat import DecodedFrame

    ws = _make_workspace(tmp_path)
    cfg = Config(theme="dark", workspace=ws)
    drv = FileReplayDriver()
    drv.open({"path": str(FX / "e2e_session.pgnlog"), "speed": "max"})
    app = _build_app(cfg=cfg, workspace=ws, driver=drv)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.query_one(TabbedContent).active = "tab-content"
        await pilot.pause()
        assert app._auto_active is False  # Auto hidden
        assert app._auto_builder is not None and app._auto_builder.count == 0
        # Frames accumulate in the capped buffer while Auto is hidden.
        for pgn in (127488, 129025):
            app._debug_buffer.push(
                DecodedFrame(timestamp=0.0, source_addr=3, pgn=pgn, name="X", fields={"V": 1.0})
            )
        assert app._auto_builder.count == 0  # not built while hidden
        app.query_one(TabbedContent).active = "tab-auto"
        await pilot.pause()
        assert app._auto_active is True
        # Rebuilt from the buffer on open (>= my two; the replay may add more).
        assert app._auto_builder.count >= 2
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
