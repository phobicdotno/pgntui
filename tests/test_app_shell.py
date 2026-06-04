import pytest

from pgntui.app import PgntuiApp
from pgntui.themes.loader import load_builtin


@pytest.mark.asyncio
async def test_app_starts_and_shows_tabs() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), container_titles=["Engine", "Nav"])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#tabs")
        assert app.query_one("#status-bar")
        assert app.query_one("#hotkey-strip")


@pytest.mark.asyncio
async def test_app_applies_theme_css() -> None:
    theme = load_builtin("dark")
    app = PgntuiApp(theme=theme, container_titles=["Engine"])
    async with app.run_test():
        assert theme.colors["bg"] in app.stylesheet.source[("theme", "theme")].content
