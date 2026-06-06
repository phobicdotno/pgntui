"""DashboardView — every page's containers on one scrolling page.

The Page → Container → Signal model authored across several page files is
rendered *together* here: all containers flow into one responsive ``Grid`` whose
column count tracks the terminal width, with a single optional global instance
selector on top. This replaces the former one-tab-per-page layout — there are no
Nav/Engine/Main tabs, just one dashboard.

Reflow on resize only changes the grid's column count; the ``GroupBox`` widgets
(and their live readings) are never rebuilt, so a terminal resize doesn't blank
the gauges.
"""

from __future__ import annotations

from collections.abc import Iterator

from textual.app import ComposeResult
from textual.containers import Grid
from textual.widget import Widget

from pgntui.pages.loader import Container, InstanceOption, Page
from pgntui.pages.view import GroupBox, GroupRule, _make_widget
from pgntui.signals.base import Signal
from pgntui.signals.widgets import AnalogInWidget, DigitalInWidget
from pgntui.themes.loader import Theme

# A signal row is ~title(20) + bar(20) + value, so give each column at least this
# many cells before adding another. Tune here to trade density vs. readability.
_MIN_COL_WIDTH = 48
_MAX_COLS = 4


class DashboardView(Widget):
    """Renders every container from every page on one page, flowed into a
    responsive K-column grid, with one global instance selector when any page
    declares NMEA instances."""

    DEFAULT_CSS = """
    DashboardView {
        height: 1fr;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
    }
    DashboardView GroupRule { height: 1; margin: 0 0 1 0; }
    DashboardView #dash-grid {
        grid-rows: auto;
        grid-gutter: 1 2;
        height: auto;
    }
    /* Inner per-container signal grids: one cell-row per signal row. */
    DashboardView GroupBox Grid {
        grid-rows: 1;
        grid-gutter: 0;
        height: auto;
    }
    DashboardView AnalogInWidget,
    DashboardView AnalogOutWidget,
    DashboardView DigitalInWidget,
    DashboardView DigitalOutWidget { height: 1; }
    /* Each container is framed in a titled border (same look as PageView). */
    DashboardView GroupBox {
        height: auto;
        border: solid $accent;
        border-title-color: $accent;
        border-title-style: bold;
        border-title-align: left;
        padding: 0 1;
        margin: 0;
    }
    """

    def __init__(
        self,
        pages: list[Page],
        signals: dict[str, Signal],
        write_enabled: bool,
        theme: Theme | None = None,
    ) -> None:
        super().__init__()
        self.pages = list(pages)
        self.signals = signals
        self.write_enabled = write_enabled
        self.theme_def = theme
        self.widgets: dict[str, Widget] = {}
        # Ordered (widget, column_span) pairs — applied in on_mount.
        self._spans: list[tuple[Widget, int]] = []
        # Refs whose owning page declares NMEA instances — the frame router
        # filters these to the active instance; everything else is unfiltered.
        self.instanced_refs: set[str] = set()
        # Instance options come from the first page that declares them (a vessel
        # typically has one instanced system — its engines).
        self.instances: tuple[InstanceOption, ...] = ()
        for page in self.pages:
            if page.instances:
                self.instances = tuple(page.instances)
                break
        self.active_index = 0
        self._instance_header: GroupRule | None = None
        self._grid: Grid | None = None

    @property
    def active_instance_id(self) -> int | None:
        """The NMEA Instance currently shown, or ``None`` if not switchable."""
        if not self.instances:
            return None
        return self.instances[self.active_index].id

    def _instance_label(self, index: int) -> str:
        opt = self.instances[index]
        return f"◀ {opt.label} ({opt.id}) ▶"

    def compose(self) -> ComposeResult:
        if self.instances:
            self._instance_header = GroupRule(
                self._instance_label(self.active_index), theme=self.theme_def
            )
            yield self._instance_header
        boxes = list(self._build_boxes())
        self._grid = Grid(*boxes, id="dash-grid")
        yield self._grid

    def _build_boxes(self) -> Iterator[GroupBox]:
        for page in self.pages:
            instanced = bool(page.instances)
            for ci, container in enumerate(page.containers):
                grid = self._build_grid(container, f"grid-{page.id}-{ci}", instanced)
                box = GroupBox(grid, id=f"box-{page.id}-{ci}")
                box.border_title = container.title
                yield box

    def _build_grid(self, container: Container, grid_id: str, instanced: bool) -> Grid:
        ordered = sorted(container.signals, key=lambda p: (p.row, p.col))
        children: list[Widget] = []
        for placement in ordered:
            sig = self.signals[placement.ref]
            w = _make_widget(sig, self.write_enabled, theme=self.theme_def)
            self.widgets[placement.ref] = w
            self._spans.append((w, placement.w))
            if instanced:
                self.instanced_refs.add(placement.ref)
            children.append(w)
        grid = Grid(*children, id=grid_id)
        grid.styles.grid_size_columns = container.cols
        return grid

    def on_mount(self) -> None:
        for widget, span in self._spans:
            widget.styles.column_span = span
        self._relayout()

    def on_resize(self) -> None:
        self._relayout()

    def _relayout(self) -> None:
        """Set the grid column count from the current width (reflow on resize)."""
        if self._grid is None:
            return
        width = self.size.width or 80
        cols = max(1, min(_MAX_COLS, width // _MIN_COL_WIDTH))
        self._grid.styles.grid_size_columns = cols

    def set_active_instance(self, index: int) -> None:
        """Switch which NMEA instance the instanced containers display (wraps)."""
        if not self.instances:
            return
        self.active_index = index % len(self.instances)
        if self._instance_header is not None:
            self._instance_header.set_title(self._instance_label(self.active_index))
        # Reset only the instanced widgets to the diffuse state so the previous
        # instance's readings don't linger as the new one's.
        for ref in self.instanced_refs:
            w = self.widgets.get(ref)
            if isinstance(w, (AnalogInWidget, DigitalInWidget)):
                w.clear()

    def apply_theme(self, theme: Theme) -> None:
        """Re-theme this view and every child in place (live theme switch)."""
        self.theme_def = theme
        if self._instance_header is not None:
            self._instance_header.theme_def = theme
            self._instance_header.refresh()
        for widget in self.widgets.values():
            widget.theme_def = theme  # type: ignore[attr-defined]
            widget.refresh()


__all__ = ["DashboardView"]
