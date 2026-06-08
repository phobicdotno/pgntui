"""Single-instance lock, the port-busy launch message, and its status display."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pgntui.__main__ import (
    _driver_open_message,
    _instance_lock_path,
    _pid_alive,
    acquire_single_instance,
    release_single_instance,
)
from pgntui.app import PgntuiApp
from pgntui.themes.loader import load_builtin


def test_pid_alive_self_and_dead() -> None:
    assert _pid_alive(os.getpid()) is True
    assert _pid_alive(0) is False
    assert _pid_alive(999_999_990) is False  # almost certainly not a live PID


def test_acquire_then_stale_takeover(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    # First acquire from this process succeeds (no other holder).
    assert acquire_single_instance(ws) is None
    assert _instance_lock_path(ws).read_text().strip() == str(os.getpid())
    # A stale lock (dead PID) is taken over, not treated as a live instance.
    _instance_lock_path(ws).write_text("999999990", encoding="utf-8")
    assert acquire_single_instance(ws) is None
    assert _instance_lock_path(ws).read_text().strip() == str(os.getpid())


def test_acquire_refuses_when_live_holder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    _instance_lock_path(ws).write_text("4242", encoding="utf-8")
    # Pretend PID 4242 is a live pgntui.
    monkeypatch.setattr("pgntui.__main__._pid_alive", lambda pid: pid == 4242)
    holder = acquire_single_instance(ws)
    assert holder == 4242  # refused; the existing live instance is reported


def test_release_only_removes_own_lock(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    acquire_single_instance(ws)  # writes our PID
    release_single_instance(ws)
    assert not _instance_lock_path(ws).exists()
    # A lock owned by someone else is left alone.
    _instance_lock_path(ws).write_text("4242", encoding="utf-8")
    release_single_instance(ws)
    assert _instance_lock_path(ws).exists()


def test_driver_open_message_distinguishes_busy() -> None:
    busy = _driver_open_message({"port": "COM4"}, PermissionError(13, "Access is denied."))
    assert "COM4" in busy and "busy" in busy and "press c" in busy.lower()
    other = _driver_open_message({"port": "COM4"}, OSError("no such file"))
    assert "Could not open COM4" in other


@pytest.mark.asyncio
async def test_startup_status_shown_in_status_bar() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), pages=[], startup_status="COM4 is busy")
    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import Static

        rendered = str(app.query_one("#status-bar", Static).render())
        assert "COM4 is busy" in rendered
