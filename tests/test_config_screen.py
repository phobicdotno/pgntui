"""Config menu (☰): theme picker with live switch + persistence, and the
``list_builtin`` / ``write_theme`` helpers it relies on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Select

from pgntui.app import ConfigScreen, PgntuiApp
from pgntui.config import load_config, write_theme
from pgntui.themes.loader import list_builtin, load_builtin

# ---- helpers ---------------------------------------------------------------


def test_list_builtin_includes_known_themes() -> None:
    ids = {tid for _, tid in list_builtin()}
    assert {"dark", "light", "amber-crt"} <= ids
    # Sorted by title, every entry is a (title, id) pair of non-empty strings.
    pairs = list_builtin()
    assert all(title and tid for title, tid in pairs)


def test_write_theme_creates_app_section(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.toml"
    write_theme(cfg_path, "amber-crt")
    assert load_config(cfg_path).theme == "amber-crt"


def test_write_theme_replaces_existing_key_and_keeps_other_sections(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        '[driver]\nname = "file-replay"\n\n[app]\ntheme = "dark"\nwrite_enabled = true\n',
        encoding="utf-8",
    )
    write_theme(cfg_path, "green-phosphor")
    text = cfg_path.read_text(encoding="utf-8")
    assert text.count("theme =") == 1
    cfg = load_config(cfg_path)
    assert cfg.theme == "green-phosphor"
    assert cfg.driver_name == "file-replay"  # untouched section preserved
    assert cfg.write_enabled is True  # untouched key preserved


# ---- the menu itself -------------------------------------------------------


@pytest.mark.asyncio
async def test_config_opens_via_button_and_key() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), pages=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#config-button")
        await pilot.pause()
        assert isinstance(app.screen, ConfigScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ConfigScreen)
        await pilot.press("s")
        await pilot.pause()
        assert isinstance(app.screen, ConfigScreen)


@pytest.mark.asyncio
async def test_theme_switch_is_live_and_reverts_on_close() -> None:
    app = PgntuiApp(theme=load_builtin("dark"), pages=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._theme.id == "dark"
        await pilot.press("s")
        await pilot.pause()
        app.screen.query_one("#theme-select", Select).value = "amber-crt"
        await pilot.pause()
        assert app._theme.id == "amber-crt"  # live preview applied
        await pilot.press("escape")  # close without saving
        await pilot.pause()
        assert app._theme.id == "dark"  # reverted


@pytest.mark.asyncio
async def test_save_persists_theme_and_keeps_preview(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "config.toml").write_text('[app]\ntheme = "dark"\n', encoding="utf-8")
    app = PgntuiApp(theme=load_builtin("dark"), pages=[], workspace=workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        app.screen.query_one("#theme-select", Select).value = "light"
        await pilot.pause()
        await pilot.click("#config-save")
        await pilot.pause()
        assert not isinstance(app.screen, ConfigScreen)
        assert app._theme.id == "light"  # preview kept after save
    assert load_config(workspace / "config.toml").theme == "light"


@pytest.mark.asyncio
async def test_apply_theme_repaints_container_views(tmp_path: Path) -> None:
    from pgntui.__main__ import _build_app, scaffold_example

    workspace = tmp_path / "ws"
    assert scaffold_example(workspace) == 0
    cfg = load_config(workspace / "config.toml")
    app = _build_app(cfg=cfg, workspace=workspace, driver=None)
    async with app.run_test(size=(110, 38)) as pilot:
        await pilot.pause()
        assert app._page_views
        app.apply_theme("amber-crt")
        await pilot.pause()
        assert app._theme.id == "amber-crt"
        for _container, view in app._page_views:
            assert view.theme_def is not None
            assert view.theme_def.id == "amber-crt"
            for w in view.widgets.values():
                assert w.theme_def.id == "amber-crt"  # type: ignore[attr-defined]
