"""Pressing q quits immediately (no Textual confirmation toast)."""

from __future__ import annotations

import pytest

from pgntui.app import PgntuiApp
from pgntui.themes.loader import load_builtin


@pytest.mark.asyncio
async def test_q_key_quits_app_immediately() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), containers=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.is_running
        await pilot.press("q")
        # Give the action loop a beat to process the exit.
        for _ in range(5):
            await pilot.pause()
            if not app.is_running:
                break
    assert not app.is_running


@pytest.mark.asyncio
async def test_ctrl_q_key_also_quits_app() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), containers=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.is_running
        await pilot.press("ctrl+q")
        for _ in range(5):
            await pilot.pause()
            if not app.is_running:
                break
    assert not app.is_running


@pytest.mark.asyncio
async def test_force_quit_action_directly() -> None:
    """The action_force_quit method should bypass any quit confirmation."""
    app = PgntuiApp(theme=load_builtin("dark"), containers=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_force_quit()
        for _ in range(5):
            await pilot.pause()
            if not app.is_running:
                break
    assert not app.is_running
