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
    PageView Grid {
        grid-rows: 1;
        grid-gutter: 0;
        height: auto;
    }
    PageView AnalogInWidget,
    PageView AnalogOutWidget,
    PageView DigitalInWidget,
    PageView DigitalOutWidget,
    PageView GroupRule {
        height: 1;
    }
    /* Each container is framed in a titled border — the container name sits in
       the top border line (e.g. ``┌─ Heading & attitude ──────┐``). */
    PageView GroupBox {
        height: auto;
        border: solid $accent;
        border-title-color: $accent;
        border-title-style: bold;
        border-title-align: left;
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
            children.append(w)
        grid = Grid(*children, id=grid_id)
        grid.styles.grid_size_columns = container.cols
        return grid

    def on_mount(self) -> None:
        for widget, span in self._spans:
            widget.styles.column_span = span

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
        for widget in self.widgets.values():
            widget.theme_def = theme  # type: ignore[attr-defined]
            widget.refresh()


__all__ = ["GroupBox", "GroupRule", "PageView"]
