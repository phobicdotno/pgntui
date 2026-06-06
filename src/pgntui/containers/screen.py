"""ContainerScreen and ContainerView — renders a Container's grid of signal widgets.

``ContainerView`` is the reusable widget that does the actual grid layout. It
can be mounted anywhere (inside a TabPane, a Screen, etc.). ``ContainerScreen``
is a thin Screen wrapper around ContainerView, kept for code that wants to
push the container as its own full-screen view.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container as TextualContainer
from textual.containers import Grid
from textual.screen import Screen
from textual.widget import Widget

from pgntui.containers.loader import Container, SignalPlacement
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


class ContainerView(Widget):
    """Grid view that renders a Container's signal widgets.

    Widgets are exposed via the ``widgets`` dict keyed by ``SignalPlacement.ref``
    so callers can update displayed values or wire write callbacks.
    """

    # Without an explicit height the view is auto-sized, and the child Grid's
    # default ``height: 1fr`` cannot resolve inside an auto parent — the grid
    # collapses and every signal widget renders at height 0 (blank tab).
    # ``grid-rows: 1`` keeps every row a single line (tight rows) and lets the
    # content pack at the top instead of stretching to fill the tab.
    DEFAULT_CSS = """
    ContainerView {
        height: 1fr;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
    }
    ContainerView Grid {
        grid-rows: 1;
        grid-gutter: 0;
        height: auto;
    }
    ContainerView AnalogInWidget,
    ContainerView AnalogOutWidget,
    ContainerView DigitalInWidget,
    ContainerView DigitalOutWidget,
    ContainerView GroupRule {
        height: 1;
    }
    /* Each signal group is framed in a titled border — the group name sits in
       the top border line (e.g. ``┌─ Heading & attitude ──────┐``). */
    ContainerView GroupBox {
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
        container: Container,
        signals: dict[str, Signal],
        write_enabled: bool,
        theme: Theme | None = None,
    ) -> None:
        super().__init__()
        self.container_def = container
        self.signals = signals
        self.write_enabled = write_enabled
        self.theme_def = theme
        self.widgets: dict[str, Widget] = {}
        # Ordered (child widget, column_span) pairs, built in compose, applied
        # in on_mount (column_span can't be set before the widget is mounted).
        self._spans: list[tuple[Widget, int]] = []
        # Instance switcher state (only used when container.instances is set).
        self.active_index = 0
        self._instance_header: GroupRule | None = None

    @property
    def active_instance_id(self) -> int | None:
        """The NMEA Instance currently shown, or ``None`` if not switchable."""
        instances = self.container_def.instances
        if not instances:
            return None
        return instances[self.active_index].id

    def _instance_label(self, index: int) -> str:
        opt = self.container_def.instances[index]
        return f"◀ {opt.label} ({opt.id}) ▶"

    def set_active_instance(self, index: int) -> None:
        """Switch which instance this container displays (wraps around)."""
        instances = self.container_def.instances
        if not instances:
            return
        self.active_index = index % len(instances)
        if self._instance_header is not None:
            self._instance_header.set_title(self._instance_label(self.active_index))
        # Clear stale readings so the previous instance's values don't linger.
        for widget in self.widgets.values():
            if isinstance(widget, AnalogInWidget):
                widget.update_value(widget.signal.min)
            elif isinstance(widget, DigitalInWidget):
                widget.update_value(0)

    def compose(self) -> ComposeResult:
        # An instance-switchable container gets a group-style header line at the
        # top showing the active source (e.g. ``├── ◀ Engine Stb (0) ▶ ──┤``).
        if self.container_def.instances:
            self._instance_header = GroupRule(
                self._instance_label(self.active_index), theme=self.theme_def
            )
            yield self._instance_header
        cols = self.container_def.cols
        groups = sorted(self.container_def.groups, key=lambda g: g.row)
        # Bucket each signal under the group whose header row is the nearest one
        # at or above it. ``None`` collects signals that sit above the first
        # group (or every signal when the container declares no groups).
        buckets: dict[int | None, list[SignalPlacement]] = {}
        for placement in self.container_def.signals:
            idx: int | None = None
            for i, g in enumerate(groups):
                if g.row <= placement.row:
                    idx = i
                else:
                    break
            buckets.setdefault(idx, []).append(placement)
        # Leading, group-less signals render in a plain grid (no frame).
        leading = buckets.get(None)
        if leading:
            yield self._build_grid(leading, cols, f"container-grid-{self.container_def.id}")
        # Every declared group becomes a titled border box around its own grid.
        for i, g in enumerate(groups):
            grid = self._build_grid(
                buckets.get(i, []), cols, f"group-grid-{self.container_def.id}-{i}"
            )
            box = GroupBox(grid, id=f"group-box-{self.container_def.id}-{i}")
            box.border_title = g.title
            yield box

    def _build_grid(self, placements: list[SignalPlacement], cols: int, grid_id: str) -> Grid:
        """Build one auto-flow Grid from ``placements`` (registering each widget
        and recording its column span for ``on_mount``)."""
        ordered = sorted(placements, key=lambda p: (p.row, p.col))
        children: list[Widget] = []
        for placement in ordered:
            sig = self.signals[placement.ref]
            w = _make_widget(sig, self.write_enabled, theme=self.theme_def)
            self.widgets[placement.ref] = w
            self._spans.append((w, placement.w))
            children.append(w)
        grid = Grid(*children, id=grid_id)
        grid.styles.grid_size_columns = cols
        return grid

    def on_mount(self) -> None:
        for widget, span in self._spans:
            widget.styles.column_span = span

    def apply_theme(self, theme: Theme) -> None:
        """Re-theme this view and every child in place (live theme switch).

        The signal widgets and group rules bake ``theme_def.colors`` into their
        ``render`` output, so swapping the reference and refreshing is enough —
        no rebuild needed.
        """
        self.theme_def = theme
        if self._instance_header is not None:
            self._instance_header.theme_def = theme
            self._instance_header.refresh()
        for widget in self.widgets.values():
            widget.theme_def = theme  # type: ignore[attr-defined]
            widget.refresh()


class GroupBox(TextualContainer):
    """A signal group framed in a titled border — the group name sits in the
    top border line, e.g. ``┌─ Heading & attitude ─────────┐``.

    Styling (border glyphs, colors, padding) lives in ``ContainerView``'s CSS;
    the border color tracks the active Textual theme via ``$accent``, so it
    repaints automatically on a live theme switch.
    """


class GroupRule(Widget):
    """Full-width separator line: ``├── Title ──────────────┤``.

    Still used for the instance-switch header (``◀ Engine Stb (0) ▶``); signal
    groups now render as :class:`GroupBox` titled borders instead.
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


class ContainerScreen(Screen[None]):
    def __init__(
        self,
        container: Container,
        signals: dict[str, Signal],
        write_enabled: bool,
        theme: Theme | None = None,
    ) -> None:
        super().__init__()
        self.container_def = container
        self.signals = signals
        self.write_enabled = write_enabled
        self.theme_def = theme
        self._view: ContainerView | None = None

    @property
    def widgets(self) -> dict[str, Widget]:
        if self._view is None:
            return {}
        return self._view.widgets

    def compose(self) -> ComposeResult:
        self._view = ContainerView(
            container=self.container_def,
            signals=self.signals,
            write_enabled=self.write_enabled,
            theme=self.theme_def,
        )
        yield self._view


__all__ = ["ContainerScreen", "ContainerView", "GroupBox", "GroupRule"]
