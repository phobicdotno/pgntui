"""The configured pgntui theme must drive Textual's chrome theme too.

pgntui themes styled widget content while Textual's own theme system styled
the header/tabs/footer — switching the pgntui theme left the chrome on
Textual defaults (and vice versa via the command palette), so the UI looked
half-themed. The app now registers the active pgntui theme as a Textual
theme and activates it, so chrome colors follow config.toml.
"""

from __future__ import annotations

import pytest

from pgntui.app import PgntuiApp
from pgntui.debug.tab import DebugBuffer
from pgntui.themes.loader import load_builtin


@pytest.mark.asyncio
async def test_app_activates_pgntui_theme_in_textual() -> None:
    theme = load_builtin("dark")
    app = PgntuiApp(theme=theme, debug_buffer=DebugBuffer())
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.theme == "pgntui-dark"
        registered = app.available_themes["pgntui-dark"]
        assert registered.primary == theme.colors["accent"]
        assert registered.background == theme.colors["bg"]
        assert registered.foreground == theme.colors["fg"]
        assert registered.warning == theme.colors["warn"]
        assert registered.error == theme.colors["alarm"]
        assert registered.success == theme.colors["ok"]


@pytest.mark.asyncio
async def test_light_builtin_registers_as_light_textual_theme() -> None:
    theme = load_builtin("light")
    app = PgntuiApp(theme=theme, debug_buffer=DebugBuffer())
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.theme == "pgntui-light"
        assert app.available_themes["pgntui-light"].dark is False
