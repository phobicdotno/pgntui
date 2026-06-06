"""About screen, titled header, and the curated changelog."""

from __future__ import annotations

import pytest

from pgntui import __version__, about
from pgntui.app import AboutScreen, PgntuiApp, TopBar
from pgntui.themes.loader import load_builtin


def test_release_notes_top_matches_version() -> None:
    # Guard: the newest changelog entry must be the shipped version, so the
    # About screen can never silently lag a release.
    assert about.RELEASE_NOTES[0][0] == __version__


def test_header_title_has_name_tagline_and_version() -> None:
    title = about.header_title()
    assert "PgnTui" in title
    assert "NMEA 2000 reader" in title
    assert f"v{__version__}" in title


def test_changelog_lines_are_short_and_versioned() -> None:
    lines = about.changelog_lines()
    assert lines, "changelog should not be empty"
    for line in lines:
        assert line.startswith("v")
        assert len(line) <= 80, f"changelog line too long: {line!r}"


@pytest.mark.asyncio
async def test_topbar_button_hover_text_contrasts_with_fill() -> None:
    # Regression: mono-ascii has accent == foreground (#ffffff), so a hover that
    # only set background painted white-on-white. The hover label must invert to
    # the theme background color and never match the (accent) fill.
    app = PgntuiApp(theme=load_builtin("mono-ascii"), pages=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.hover("#config-button")
        await pilot.pause()
        btn = app.query_one("#config-button")
        assert btn.styles.color.rgb != btn.styles.background.rgb, "hover text invisible on fill"
        assert btn.styles.color.rgb == (0, 0, 0), "mono-ascii hover label should be black"


@pytest.mark.asyncio
async def test_top_bar_shows_title_with_version() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), pages=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(TopBar)
        title = app.query_one("#app-title")
        rendered = str(title.render())  # type: ignore[attr-defined]
        assert bar is not None
        assert f"v{__version__}" in rendered
        assert "PgnTui" in rendered


@pytest.mark.asyncio
async def test_about_opens_via_key_and_closes() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), pages=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, AboutScreen)
        # The dialog shows the version and at least one changelog line.
        body = str(app.screen.query_one("#about-head").render())  # type: ignore[attr-defined]
        assert __version__ in body
        assert about.RELEASE_NOTES[0][1] in body
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, AboutScreen)


@pytest.mark.asyncio
async def test_about_opens_via_button_click() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), pages=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#about-button")
        await pilot.pause()
        assert isinstance(app.screen, AboutScreen)


@pytest.mark.asyncio
async def test_about_does_not_stack_duplicates() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), pages=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_about()
        await pilot.pause()
        app.action_about()  # second call is a no-op while already open
        await pilot.pause()
        about_screens = [s for s in app.screen_stack if isinstance(s, AboutScreen)]
        assert len(about_screens) == 1
