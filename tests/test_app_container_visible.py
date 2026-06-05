"""Regression: example-workspace signal widgets must be visible on screen.

The scaffolded example workspace produced a blank Main tab: ``ContainerView``
set no height, so its child ``Grid`` (``height: 1fr``) collapsed inside the
auto-height parent — the grid got 1 screen line for 3 rows and the row-0
widgets rendered at height 0. Existing tests only asserted widgets were
*mounted*; this asserts every placed widget occupies non-zero screen area
when the app runs against the real example workspace.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pgntui.__main__ import _build_app, scaffold_example
from pgntui.config import load_config
from pgntui.signals.widgets import (
    AnalogInWidget,
    AnalogOutWidget,
    DigitalInWidget,
    DigitalOutWidget,
)

_WIDGET_TYPES = (AnalogInWidget, AnalogOutWidget, DigitalInWidget, DigitalOutWidget)


@pytest.mark.asyncio
async def test_example_workspace_widgets_have_nonzero_screen_area(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    assert scaffold_example(workspace) == 0
    cfg = load_config(workspace / "config.toml")
    app = _build_app(cfg=cfg, workspace=workspace, driver=None)
    async with app.run_test(size=(110, 30)) as pilot:
        await pilot.pause()
        widgets = [w for t in _WIDGET_TYPES for w in app.query(t)]
        assert widgets, "example workspace produced no signal widgets"
        for w in widgets:
            assert w.region.height > 0, f"{w.signal.id} collapsed to zero height"
            assert w.region.width > 0, f"{w.signal.id} collapsed to zero width"
