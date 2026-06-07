"""Regression: example-workspace signal widgets must be visible on screen.

The scaffolded example workspace produced a blank Main tab: ``PageView``
set no height, so its child ``Grid`` (``height: 1fr``) collapsed inside the
auto-height parent — the grid got 1 screen line for 3 rows and the row-0
widgets rendered at height 0. Existing tests only asserted widgets were
*mounted*; this asserts every placed widget occupies non-zero screen area
when its tab is active. (Widgets in inactive tabs legitimately have zero
region — each tab is activated before its widgets are checked.)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import TabbedContent

from pgntui.__main__ import _build_app, scaffold_example
from pgntui.config import load_config


@pytest.mark.asyncio
async def test_example_workspace_widgets_have_nonzero_screen_area(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    assert scaffold_example(workspace) == 0
    cfg = load_config(workspace / "config.toml")
    app = _build_app(cfg=cfg, workspace=workspace, driver=None)
    # Tall terminal so every stacked section fits without scrolling — then every
    # placed widget must occupy non-zero screen area.
    async with app.run_test(size=(120, 70)) as pilot:
        await pilot.pause()
        tabs = app.query_one(TabbedContent)
        assert app._page_views, "example workspace produced no page views"
        # All source pages are now sections inside the single content tab.
        tabs.active = "tab-content"
        await pilot.pause()
        for page, view in app._page_views:
            assert view.widgets, f"page {page.id} has no widgets"
            for ref, w in view.widgets.items():
                assert w.region.height > 0, f"{page.id}/{ref} collapsed to zero height"
                assert w.region.width > 0, f"{page.id}/{ref} collapsed to zero width"
