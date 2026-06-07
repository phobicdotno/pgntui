"""PageView — renders a Page as a vertical stack of titled Container boxes.

A :class:`Page` owns one or more :class:`~pgntui.pages.loader.Container` boxes;
each Container owns a grid of signal widgets. ``PageView`` mounts the optional
page-level instance header (``◀ Engine Stb (0) ▶``) followed by one
:class:`GroupBox` per container. Widgets are exposed via the ``widgets`` dict
(keyed by ``SignalPlacement.ref``) so callers can push values / wire writes.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container as TextualContainer
from textual.containers import Grid
from textual.widget import Widget

from pgntui.pages.loader import Container, Page
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


# Screen width (columns) at/above which the three-column layout [3] is offered,
# so each of the three columns stays wide enough to be usable.
_THREE_COL_MIN = 120


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
    /* Rows are FIXED at 1 cell so a multi-column grid stays tight. (An ``auto``
       row track stretches to fill the box height, which spreads rows apart.)
       ``_refresh_grid_rows`` bumps just an expanded row to 2 with a fixed value,
       so only that row grows and nothing stretches. */
    PageView Grid {
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
        margin: 0 0 1 0;
    }
    """

    def __init__(
        self,
        page: Page,
        signals: dict[str, Signal],
        write_enabled: bool,
        theme: Theme | None = None,
    ) -> None:
        super().__init__()
        self.page = page
        self.signals = signals
        self.write_enabled = write_enabled
        self.theme_def = theme
        self.widgets: dict[str, Widget] = {}
        # Ordered (child widget, column_span) pairs, built in compose, applied in
        # on_mount (column_span can't be set before the widget is mounted).
        self._spans: list[tuple[Widget, int]] = []
        # Per-container grids + each widget's grid-row index, so an expanded
        # input row can be bumped to height 2 without ``auto`` stretching.
        self._grids: list[Grid] = []
        self._boxes: list[GroupBox] = []
        self._row_of_widget: dict[Widget, int] = {}
        # Column layout: None = the page's authored layout; 1/2/3 = that many
        # equal columns. Toggled by [1] / [2] / [3].
        self._layout_cols: int | None = None
        self._span_of_widget: dict[Widget, int] = {}
        # Instance switcher state (only used when the page declares instances).
        self.active_index = 0
        self._instance_header: GroupRule | None = None

    @property
    def active_instance_id(self) -> int | None:
        """The NMEA Instance currently shown, or ``None`` if not switchable."""
        if not self.page.instances:
            return None
        return self.page.instances[self.active_index].id

    def _instance_label(self, index: int) -> str:
        opt = self.page.instances[index]
        return f"◀ {opt.label} ({opt.id}) ▶"

    def set_active_instance(self, index: int) -> None:
        """Switch which instance this page displays (wraps around)."""
        if not self.page.instances:
            return
        self.active_index = index % len(self.page.instances)
        if self._instance_header is not None:
            self._instance_header.set_title(self._instance_label(self.active_index))
        # Reset readings to the diffuse (no-data) state so the previous
        # instance's values don't linger as if they belonged to the new one.
        for widget in self.widgets.values():
            if isinstance(widget, (AnalogInWidget, DigitalInWidget)):
                widget.clear()

    def compose(self) -> ComposeResult:
        # A page with instances gets a header line showing the active source.
        if self.page.instances:
            self._instance_header = GroupRule(
                self._instance_label(self.active_index), theme=self.theme_def
            )
            yield self._instance_header
        for ci, container in enumerate(self.page.containers):
            grid = self._build_grid(container, f"grid-{self.page.id}-{ci}")
            box = GroupBox(grid, id=f"box-{self.page.id}-{ci}")
            box.border_title = container.title
            box.border_subtitle = "[1] [2]"  # [3] added on mount/resize when wide
            self._boxes.append(box)
            yield box

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
        self._update_hints()

    def on_resize(self) -> None:
        # Show/hide the [3] hint as the terminal crosses the width threshold.
        self._update_hints()

    def _three_col_allowed(self) -> bool:
        """True when the screen is wide enough for three usable columns."""
        try:
            return self.app.size.width >= _THREE_COL_MIN
        except Exception:  # pragma: no cover - not mounted
            return False

    def _update_hints(self) -> None:
        hint = "[1] [2] [3]" if self._three_col_allowed() else "[1] [2]"
        for box in self._boxes:
            box.border_subtitle = hint

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
        box.border_subtitle = "[1] [2]"
        self._boxes.append(box)
        self.mount(box)
        self._update_hints()

    def _refresh_grid_rows(self) -> None:
        """Resize each grid's row tracks so an expanded input row is 2 cells tall
        and every other row stays 1.

        Fixed values are used (never ``auto``): an ``auto`` row track stretches to
        fill the box height, spreading the rows apart, whereas fixed values keep
        the grid exactly as tall as its content. Called whenever a signal toggles
        its sparkline (see ``signals.widgets._notify_layout``).
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
            grid.styles.grid_rows = " ".join(
                "2" if r in expanded_rows else "1" for r in range(max_row + 1)
            )

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

    def apply_theme(self, theme: Theme) -> None:
        """Re-theme this view and every child in place (live theme switch).

        The signal widgets and the instance header bake ``theme_def.colors`` into
        their ``render`` output, so swapping the reference and refreshing is
        enough — no rebuild needed.
        """
        self.theme_def = theme
        if self._instance_header is not None:
            self._instance_header.theme_def = theme
            self._instance_header.refresh()
        # _row_of_widget covers authored AND runtime (Auto-page) rows, whereas
        # self.widgets has only the authored ones — so a live theme switch
        # reaches the Auto page's widgets too.
        for widget in self._row_of_widget:
            widget.theme_def = theme  # type: ignore[attr-defined]
            widget.refresh()


__all__ = ["GroupBox", "GroupRule", "PageView"]
