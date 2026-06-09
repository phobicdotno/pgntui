"""Regression tests for the top-bar dropdown menu lifecycle.

The dropdown is a single floating ``MenuDropdown`` with a fixed id mounted on
the screen. ``widget.remove()`` is asynchronous in Textual, so opening a second
menu before the first one's prune drained used to mount a second widget sharing
that id and crash with ``DuplicateIds``. These tests pin the robust behaviour:
at most one dropdown exists at any time, regardless of how fast menus are opened.
"""

from __future__ import annotations

import pytest

from pgntui.app import MenuDropdown, MenuItem, PgntuiApp, _mnemonic_index
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalRouter
from pgntui.pages.loader import Container, Page, SignalPlacement
from pgntui.signals.base import AnalogIn
from pgntui.themes.loader import load_builtin

_ITEMS_A = (("Alpha", "about", "A"),)
_ITEMS_B = (("Beta", "help", "B"),)


def _app() -> PgntuiApp:
    rpm = AnalogIn(
        id="rpm",
        type="analog_in",
        title="RPM",
        pgn=127488,
        field="Engine Speed",
        min=0,
        max=6000,
        smoothing=0.0,
    )
    page = Page(
        id="eng",
        title="Engine",
        containers=(
            Container(title="Drive", cols=12, signals=(SignalPlacement("rpm", 0, 0, 12),)),
        ),
    )
    router = SignalRouter()
    return PgntuiApp(
        theme=load_builtin("dark"),
        signals={"rpm": rpm},
        pages=[page],
        decoder=CanboatDecoder.load_bundled(),
        router=router,
        debug_buffer=DebugBuffer(),
    )


def test_mnemonic_index_finds_shortcut_letter() -> None:
    assert _mnemonic_index("Record on/off", "R") == 0  # first R
    assert _mnemonic_index("Connect…", "C") == 0
    assert _mnemonic_index("About", "A") == 0
    # Case-insensitive, first occurrence.
    assert _mnemonic_index("Settings…", "S") == 0
    # Non-letter shortcuts (e.g. ? for help) and absent letters -> no highlight.
    assert _mnemonic_index("Keyboard help", "?") is None
    assert _mnemonic_index("Quit", "Z") is None


def test_menu_item_inverts_the_shortcut_letter() -> None:
    item = MenuItem("Record on/off", "R", "toggle_record", width=20)
    text = item.render()
    # The visible row is the padded label followed by the right-aligned key.
    assert text.plain == f"{'Record on/off':<20}   R"
    # Exactly the mnemonic letter carries the reverse style.
    reverse_spans = [s for s in text.spans if "reverse" in (s.style or "")]
    assert len(reverse_spans) == 1
    span = reverse_spans[0]
    assert (span.start, span.end) == (0, 1)
    assert text.plain[span.start : span.end] == "R"


def test_menu_item_without_mnemonic_has_no_reverse_span() -> None:
    item = MenuItem("Keyboard help", "?", "help", width=20)
    text = item.render()
    assert not [s for s in text.spans if "reverse" in (s.style or "")]


@pytest.mark.asyncio
async def test_opening_a_second_menu_before_prune_does_not_duplicate() -> None:
    app = _app()
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        # Open one menu, then a different one without pausing in between, so the
        # first dropdown's async prune has not yet run. The old code mounted a
        # second dropdown sharing a fixed id here and raised DuplicateIds; the
        # fixed code (no fixed id) keeps exactly one dropdown after the prune.
        app.toggle_menu("View", _ITEMS_A, 0)
        app.toggle_menu("File", _ITEMS_B, 10)
        await pilot.pause()
        assert len(app.screen.query(MenuDropdown)) == 1
        assert app._open_menu_name == "File"


@pytest.mark.asyncio
async def test_toggling_the_same_menu_closes_it() -> None:
    app = _app()
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        app.toggle_menu("View", _ITEMS_A, 0)
        assert len(app.screen.query(MenuDropdown)) == 1
        app.toggle_menu("View", _ITEMS_A, 0)
        await pilot.pause()
        assert len(app.screen.query(MenuDropdown)) == 0
        assert app._open_menu_name is None


@pytest.mark.asyncio
async def test_close_menu_removes_every_stray_dropdown() -> None:
    app = _app()
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        app.toggle_menu("View", _ITEMS_A, 0)
        app.close_menu()
        await pilot.pause()
        assert len(app.screen.query(MenuDropdown)) == 0
        assert app._menu_dropdown is None
