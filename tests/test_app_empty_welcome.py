"""Empty-workspace welcome panel is shown in the Debug tab when no containers exist."""

from __future__ import annotations

import pytest
from textual.widgets import Static

from pgntui.app import PgntuiApp
from pgntui.themes.loader import load_builtin


@pytest.mark.asyncio
async def test_empty_workspace_shows_welcome_panel() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), containers=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        welcome = app.query_one("#welcome", Static)
        assert welcome is not None
        # The welcome blurb must point the user at --example to scaffold a workspace.
        rendered = str(welcome.render())
        assert "pgntui --example" in rendered
        assert "pgntui" in rendered


@pytest.mark.asyncio
async def test_welcome_panel_hidden_when_containers_are_present() -> None:
    """With at least one container, the welcome panel must not appear — the user
    already has a working workspace."""
    app = PgntuiApp(theme=load_builtin("dark"), container_titles=["Engine"])
    async with app.run_test() as pilot:
        await pilot.pause()
        # query() returns DOMQuery — len == 0 means not mounted.
        assert len(app.query("#welcome")) == 0


@pytest.mark.asyncio
async def test_bottom_strips_visible_on_empty_workspace() -> None:
    """Hotkey strip and status bar must still be reachable when the workspace is
    empty (the original bug had TabbedContent absorbing all vertical space)."""
    app = PgntuiApp(theme=load_builtin("dark"), containers=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        hotkeys = app.query_one("#hotkey-strip", Static)
        status = app.query_one("#status-bar", Static)
        assert hotkeys is not None
        assert status is not None
        # Sanity: hotkey strip text matches the actual bindings.
        rendered = str(hotkeys.render())
        assert "[Tab]" in rendered
        assert "[Q]" in rendered
