"""PageView — renders a Page as a vertical stack of titled Container boxes.

A :class:`Page` owns one or more :class:`~pgntui.pages.loader.Container` boxes;
each Container owns a grid of signal widgets. ``PageView`` mounts the optional
page-level instance header (``◀ Engine Stb (0) ▶``) followed by one
:class:`GroupBox` per container. Widgets are exposed via the ``widgets`` dict
(keyed by ``SignalPlacement.ref``) so callers can push values / wire writes.
"""

from __future__ import annotations

from collections.abc import Callable

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Container as TextualContainer
from textual.containers import Grid
from textual.widget import Widget

from pgntui.pages.loader import Container, InstanceOption, Page
from pgntui.signals.base import AnalogIn, AnalogOut, DigitalIn, DigitalOut, Signal
from pgntui.signals.widgets import (
    AnalogInWidget,
    AnalogOutWidget,
    DigitalInWidget,
    DigitalOutWidget,
)
from pgntui.themes.loader import Theme


def _make_widget(sig: Signal, write_enabled: bool, theme: Theme | None = None) -> Widget:
    if isinstance(sig, AnalogIn):
        return AnalogInWidget(sig, theme=theme)
    if isinstance(sig, AnalogOut):
        return AnalogOutWidget(sig, write_enabled=write_enabled, theme=theme)
    if isinstance(sig, DigitalIn):
        return DigitalInWidget(sig, theme=theme)
    if isinstance(sig, DigitalOut):
        return DigitalOutWidget(sig, write_enabled=write_enabled, theme=theme)
    raise TypeError(f"Unknown signal type: {type(sig).__name__}")


class GroupBox(TextualContainer):
    """A Container rendered as a titled border — the container name sits in the
    top border line, e.g. ``┌─ Heading & attitude ─────────┐``.

    Styling (border glyphs, colors, padding) lives in :class:`PageView`'s CSS;
    the border color tracks the active Textual theme via ``$accent``, so it
    repaints automatically on a live theme switch.
    """


class GroupRule(Widget):
    """Full-width separator line: ``├── Title ──────────────┤``.

    Used for the page-level instance-switch header (``◀ Engine Stb (0) ▶``);
    containers themselves render as :class:`GroupBox` titled borders.
    """

    def __init__(self, title: str, theme: Theme | None = None) -> None:
        super().__init__()
        self.title = title
        self.theme_def = theme
        self._width = 0

    def set_width(self, width: int) -> None:
        self._width = width

    def set_title(self, title: str) -> None:
        self.title = title
        self.refresh()

    def on_resize(self) -> None:
        self._width = self.size.width

    def _line(self, width: int) -> tuple[str, str, str]:
        left = "├── "
        label = f"{self.title} "
        fill = max(width - len(left) - len(label) - 1, 0)
        return left, label, ("─" * fill) + "┤"

    def render(self) -> Text | str:
        width = self._width or self.size.width or (len(self.title) + 8)
        left, label, right = self._line(width)
        if self.theme_def is None:
            return f"{left}{label}{right}"
        c = self.theme_def.colors
        text = Text()
        text.append(left, style=c["border"])
        text.append(label, style=f"bold {c['accent']}")
        text.append(right, style=c["border"])
        return text


class InstanceBar(Widget):
    """Clickable instance selector rendered as a rule line, e.g.
    ``── Engine Stb ─────── 0  1  2  3``. Clicking a number switches the section
    to that NMEA instance and inverts (highlights) the chosen number; the label
    shows the selected source. Replaces a plain header inside an
    instance-switchable section. The , / . keys drive the same switch.
    """

    DEFAULT_CSS = "InstanceBar { height: 1; }"

    def __init__(
        self,
        instances: tuple[InstanceOption, ...],
        active_index: int,
        on_pick: Callable[[int], None],
        theme: Theme | None = None,
    ) -> None:
        super().__init__()
        self._instances = instances
        self.active_index = active_index
        self._on_pick = on_pick
        self.theme_def = theme
        # Widget-relative x-range of each number, recomputed each render so a
        # click can be mapped back to the instance it landed on.
        self._ranges: list[tuple[int, int]] = []
        self._width = 0

    def on_resize(self) -> None:
        self._width = self.size.width
        self.refresh()

    def set_active(self, index: int) -> None:
        self.active_index = index % len(self._instances)
        self.refresh()

    def render(self) -> Text | str:
        width = self._width or self.size.width or 40
        label = self._instances[self.active_index].label
        left = f"── {label} "
        segs = [f" {opt.id} " for opt in self._instances]
        fill = max(width - len(left) - sum(len(s) for s in segs), 0)
        self._ranges = []
        x = len(left) + fill
        for s in segs:
            self._ranges.append((x, x + len(s)))
            x += len(s)
        c = self.theme_def.colors if self.theme_def is not None else None
        text = Text()
        if c is not None:
            text.append(left, style=f"bold {c['accent']}")
            text.append("─" * fill, style=c["border"])
            for i, s in enumerate(segs):
                style = f"reverse bold {c['accent']}" if i == self.active_index else c["accent"]
                text.append(s, style=style)
        else:
            text.append(left + "─" * fill)
            for i, s in enumerate(segs):
                text.append(s, style="reverse bold" if i == self.active_index else "")
        return text

    def _index_at(self, x: int) -> int | None:
        """The instance whose number occupies column ``x`` (widget-relative)."""
        for i, (start, end) in enumerate(self._ranges):
            if start <= x < end:
                return i
        return None

    def on_click(self, event: events.Click) -> None:
        index = self._index_at(event.x)
        if index is not None:
            self._on_pick(index)


# Screen width (columns) at/above which the three-column layout [3] is offered,
# so each of the three columns stays wide enough to be usable.
_THREE_COL_MIN = 120

# Minimum width (columns) budgeted per group box when arranging the container
# boxes into side-by-side columns with Shift+1/2/3: two group columns need ~80
# cols, three need ~120 — mirroring the per-signal-column budget above.
_GROUP_COL_MIN_WIDTH = 40


class PageView(Widget):
    """Renders one Page: an optional page-level instance header, then a vertical
    scroll of its Containers, each a titled :class:`GroupBox` wrapping a grid."""

    DEFAULT_CSS = """
    PageView {
        height: 1fr;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
    }
    /* Signal grids live INSIDE each GroupBox. Rows are FIXED at 1 cell so a
       multi-column grid stays tight. (An ``auto`` row track stretches to fill the
       box height, which spreads rows apart.) ``_refresh_grid_rows`` bumps just an
       expanded row to 2 with a fixed value, so only that row grows and nothing
       stretches. The outer box-wrapping grid is styled in code, not here. */
    PageView GroupBox Grid {
        grid-rows: 1;
        grid-gutter: 0;
        height: auto;
    }
    /* Collapsed inputs are one line; an expanded input gets the ``expanded``
       class -> two lines (signal row + sparkline). */
    PageView AnalogInWidget,
    PageView DigitalInWidget {
        height: 1;
    }
    PageView AnalogInWidget.expanded,
    PageView DigitalInWidget.expanded {
        height: 2;
    }
    PageView AnalogOutWidget,
    PageView DigitalOutWidget,
    PageView GroupRule {
        height: 1;
    }
    PageView AnalogInWidget:focus,
    PageView DigitalInWidget:focus {
        background: $boost;
    }
    /* Each container is framed in a titled border — the container name sits in
       the top border line (e.g. ``┌─ Heading & attitude ──────┐``). */
    PageView GroupBox {
        height: auto;
        border: solid $accent;
        border-title-color: $accent;
        border-title-style: bold;
        border-title-align: left;
        border-subtitle-color: $accent;
        border-subtitle-align: right;
        padding: 0 1;
        /* Spacing between boxes comes from the box grid's gutter (set in code),
           not a margin — a margin eats into the grid cell and clips the box. */
        margin: 0;
    }
    /* Section (page) boxes use a DOUBLE border (vs the container boxes' solid)
       so they stand out as the outer frame on every theme — keeping the theme's
       own $accent colour instead of a fixed second hue. */
    PageView GroupBox.section {
        border: double $accent;
    }
    """

    def __init__(
        self,
        page: Page,
        signals: dict[str, Signal],
        write_enabled: bool,
        theme: Theme | None = None,
        section_title: str | None = None,
    ) -> None:
        super().__init__()
        self.page = page
        self.signals = signals
        self.write_enabled = write_enabled
        self.theme_def = theme
        # When several pages are stacked under one tab, each is wrapped in its own
        # titled box (``┌─ Nav ─┐ … └──┘``) labelled with this, enclosing the
        # page's container boxes.
        self.section_title = section_title
        self._section_box: GroupBox | None = None
        self.widgets: dict[str, Widget] = {}
        # Ordered (child widget, column_span) pairs, built in compose, applied in
        # on_mount (column_span can't be set before the widget is mounted).
        self._spans: list[tuple[Widget, int]] = []
        # Per-container grids + each widget's grid-row index, so an expanded
        # input row can be bumped to height 2 without ``auto`` stretching.
        self._grids: list[Grid] = []
        self._boxes: list[GroupBox] = []
        # The single Grid that holds every container box, so Shift+1/2/3 can
        # arrange the boxes into 1/2/3 columns across the page. Built in compose.
        self._box_grid: Grid | None = None
        # Each box's pinned height (signal rows + border) so the box grid's row
        # tracks can be sized explicitly — its ``auto`` rows under-measure boxes.
        self._box_height: dict[GroupBox, int] = {}
        # This view's total content height, pinned in _size_box_grid_rows so the
        # section measures correctly inside a page-grid cell (Ctrl+1/2/3).
        self._content_height: int = 0
        self._row_of_widget: dict[Widget, int] = {}
        # Signal-column layout: None = the page's authored layout; 1/2/3 = that
        # many equal columns within each box. Toggled by [1] / [2] / [3].
        self._layout_cols: int | None = None
        # Group-column layout: how many container boxes sit side by side across
        # the page (Shift+1/2/3). 1 = the classic single stacked column.
        self._group_cols: int = 1
        self._span_of_widget: dict[Widget, int] = {}
        # Instance switcher state (only used when the page declares instances).
        self.active_index = 0
        self._instance_header: InstanceBar | None = None

    @property
    def active_instance_id(self) -> int | None:
        """The NMEA Instance currently shown, or ``None`` if not switchable."""
        if not self.page.instances:
            return None
        return self.page.instances[self.active_index].id

    def _pick_instance(self, index: int) -> None:
        """Switch instance from a click on the InstanceBar's number."""
        self.set_active_instance(index)

    def set_active_instance(self, index: int) -> None:
        """Switch which instance this page displays (wraps around)."""
        if not self.page.instances:
            return
        self.active_index = index % len(self.page.instances)
        if self._instance_header is not None:
            self._instance_header.set_active(self.active_index)
        # Reset readings to the diffuse (no-data) state so the previous
        # instance's values don't linger as if they belonged to the new one.
        for widget in self.widgets.values():
            if isinstance(widget, (AnalogInWidget, DigitalInWidget)):
                widget.clear()

    def compose(self) -> ComposeResult:
        # Inner content: the optional instance header, then one Grid holding every
        # container box (so Shift+1/2/3 can lay the boxes out in 1/2/3 columns).
        inner: list[Widget] = []
        if self.page.instances:
            self._instance_header = InstanceBar(
                self.page.instances,
                self.active_index,
                self._pick_instance,
                theme=self.theme_def,
            )
            inner.append(self._instance_header)
        boxes: list[GroupBox] = []
        for ci, container in enumerate(self.page.containers):
            grid = self._build_grid(container, f"grid-{self.page.id}-{ci}")
            box = GroupBox(grid, id=f"box-{self.page.id}-{ci}")
            box.border_title = container.title
            self._boxes.append(box)
            boxes.append(box)
        # height:auto keeps the grid exactly content-tall so its rows never stretch
        # (Grid defaults to height:1fr); gutters give 1-cell gaps between boxes.
        self._box_grid = Grid(*boxes, id=f"boxgrid-{self.page.id}")
        self._box_grid.styles.grid_size_columns = self._group_cols
        self._box_grid.styles.height = "auto"
        self._box_grid.styles.grid_gutter_vertical = 1
        self._box_grid.styles.grid_gutter_horizontal = 1
        inner.append(self._box_grid)
        if self.section_title:
            # Enclose the whole section in its own titled box (┌─ Nav ─┐ … └──┘),
            # nesting the container boxes inside it.
            self._section_box = GroupBox(*inner, id=f"section-{self.page.id}", classes="section")
            self._section_box.border_title = self.section_title
            yield self._section_box
        else:
            yield from inner

    def _build_grid(self, container: Container, grid_id: str) -> Grid:
        """Build one auto-flow Grid from a container's placements (registering
        each widget and recording its column span for ``on_mount``)."""
        ordered = sorted(container.signals, key=lambda p: (p.row, p.col))
        children: list[Widget] = []
        for placement in ordered:
            sig = self.signals[placement.ref]
            w = _make_widget(sig, self.write_enabled, theme=self.theme_def)
            self.widgets[placement.ref] = w
            self._spans.append((w, placement.w))
            self._row_of_widget[w] = placement.row
            self._span_of_widget[w] = placement.w
            children.append(w)
        grid = Grid(*children, id=grid_id)
        grid.styles.grid_size_columns = container.cols
        self._grids.append(grid)
        return grid

    def on_mount(self) -> None:
        for widget, span in self._spans:
            widget.styles.column_span = span
        # Pin box + box-grid heights from the start (auto rows clip them otherwise).
        self._refresh_grid_rows()

    def _three_col_allowed(self) -> bool:
        """True when the screen is wide enough for three usable signal columns."""
        try:
            return self.app.size.width >= _THREE_COL_MIN
        except Exception:  # pragma: no cover - not mounted
            return False

    def _group_cols_allowed(self, n: int) -> bool:
        """True when the screen is wide enough to put ``n`` group boxes side by
        side (each kept at least ``_GROUP_COL_MIN_WIDTH`` columns wide)."""
        if n <= 1:
            return True
        try:
            return self.app.size.width >= n * _GROUP_COL_MIN_WIDTH
        except Exception:  # pragma: no cover - not mounted
            return False

    def add_generated_container(self, title: str, rows: list[Widget]) -> None:
        """Mount a runtime-built container (used by the Auto page) and register
        its grid + rows so the sparkline row-sizing and the [1]/[2] toggle apply.
        Fields stack one per row by default."""
        grid = Grid(*rows, id=f"auto-grid-{len(self._grids)}")
        cols = self._layout_cols if self._layout_cols is not None else 1
        grid.styles.grid_size_columns = cols
        if self._layout_cols is not None:
            grid.styles.grid_columns = "1fr"
        self._grids.append(grid)
        for i, w in enumerate(rows):
            self._row_of_widget[w] = i
            self._span_of_widget[w] = 1
        box = GroupBox(grid)
        box.border_title = title
        self._boxes.append(box)
        # Pin this box's height now (its grid isn't mounted yet, so _refresh can't
        # read grid.parent): rows = signals / current signal-column count.
        effective_cols = self._layout_cols or 1
        n_rows = (len(rows) + effective_cols - 1) // effective_cols
        height = n_rows + 2  # + top/bottom border
        box.styles.height = height
        self._box_height[box] = height
        # Mount into the shared box grid so the Auto page's boxes also follow the
        # current Shift+1/2/3 group-column arrangement.
        if self._box_grid is not None:
            self._box_grid.mount(box)
        else:  # pragma: no cover - the box grid is always built in compose
            self.mount(box)
        self._size_box_grid_rows()

    def _refresh_grid_rows(self) -> None:
        """Resize each grid's row tracks so an expanded input row is 2 cells tall
        and every other row stays 1, then pin each box and the box grid to match.

        Fixed values are used (never ``auto``): an ``auto`` row track stretches to
        fill the box height, spreading the rows apart, whereas fixed values keep
        the grid exactly as tall as its content. The box grid's ``auto`` rows have
        the opposite failure — they under-measure a box to its first signal row,
        clipping the rest — so its tracks are pinned here too. Called whenever a
        signal toggles its sparkline (see ``signals.widgets._notify_layout``), on
        mount, and on a layout change.
        """
        for grid in self._grids:
            max_row = -1
            expanded_rows: set[int] = set()
            for ordinal, child in enumerate(grid.children):
                # Uniform-column modes lay widgets out in order, so the row index
                # is ordinal // cols; the authored layout uses the authored row.
                if self._layout_cols is None:
                    row = self._row_of_widget.get(child)
                else:
                    row = ordinal // self._layout_cols
                if row is None:
                    continue
                max_row = max(max_row, row)
                if getattr(child, "expanded", False):
                    expanded_rows.add(row)
            if max_row < 0:
                continue
            sizes = ["2" if r in expanded_rows else "1" for r in range(max_row + 1)]
            grid.styles.grid_rows = " ".join(sizes)
            # Pin the wrapping box to its exact content height (signal rows + the
            # top/bottom border) so the box grid's cell can't clip it.
            box = grid.parent
            if isinstance(box, GroupBox):
                height = sum(int(s) for s in sizes) + 2
                box.styles.height = height
                self._box_height[box] = height
        self._size_box_grid_rows()

    def _size_box_grid_rows(self) -> None:
        """Pin the box grid's row tracks to the boxes' real heights so each page
        row is as tall as the tallest box in it (its ``auto`` rows under-measure
        once there are several rows), then pin this view's own height so a section
        measures correctly inside a page-grid cell (Ctrl+1/2/3)."""
        if self._box_grid is None:
            return
        n = max(self._group_cols, 1)
        heights = [self._box_height[b] for b in self._boxes if b in self._box_height]
        if not heights:
            return
        row_sizes = [max(heights[i : i + n]) for i in range(0, len(heights), n)]
        self._box_grid.styles.grid_rows = " ".join(str(h) for h in row_sizes)
        # box-grid rows + 1-cell gutters between them, + instance header, + the
        # section box border (when this view is a titled section).
        total = sum(row_sizes) + max(len(row_sizes) - 1, 0)
        if self._instance_header is not None:
            total += 1
        if self.section_title:
            total += 2
            self.styles.height = total
        self._content_height = total

    def set_columns(self, n: int) -> None:
        """Lay the page out in ``n`` equal columns: [1] one full-width column,
        [2] two 50% columns, [3] three (only when the screen is wide enough).
        Uniform — each widget spans one column — so columns fill evenly and bars
        line up."""
        if n == 3 and not self._three_col_allowed():
            return  # three columns only on a wide enough screen
        self._layout_cols = n
        for grid in self._grids:
            grid.styles.grid_size_columns = n
            grid.styles.grid_columns = "1fr"  # equal-width columns
        for widget in self._span_of_widget:
            widget.styles.column_span = 1
        self._refresh_grid_rows()

    def set_group_columns(self, n: int) -> None:
        """Arrange the container boxes into ``n`` columns across the page
        (Shift+1/2/3) and auto-pick the signal density inside each box so it stays
        readable as the boxes narrow: 1 group column -> 3 signal columns, 2 -> 2,
        3 -> 1. No-op when the screen is too narrow for ``n`` group columns."""
        if not self._group_cols_allowed(n):
            return
        self._group_cols = n
        if self._box_grid is not None:
            self._box_grid.styles.grid_size_columns = n
            self._box_grid.styles.grid_columns = "1fr"  # equal-width group columns
        # More group columns -> fewer signal columns. Routed through set_columns so
        # the three-signal-column case still respects its own width gate.
        self.set_columns(4 - n)

    def apply_theme(self, theme: Theme) -> None:
        """Re-theme this view and every child in place (live theme switch).

        The signal widgets and the instance header bake ``theme_def.colors`` into
        their ``render`` output, so swapping the reference and refreshing is
        enough — no rebuild needed.
        """
        self.theme_def = theme
        # The section box is a GroupBox — its border tracks $accent via CSS, so it
        # re-themes automatically; only the GroupRule instance header bakes colors.
        if self._instance_header is not None:
            self._instance_header.theme_def = theme
            self._instance_header.refresh()
        # _row_of_widget covers authored AND runtime (Auto-page) rows, whereas
        # self.widgets has only the authored ones — so a live theme switch
        # reaches the Auto page's widgets too.
        for widget in self._row_of_widget:
            widget.theme_def = theme  # type: ignore[attr-defined]
            widget.refresh()


__all__ = ["GroupBox", "GroupRule", "InstanceBar", "PageView"]
