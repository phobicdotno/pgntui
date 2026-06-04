"""ContainerScreen and ContainerView — renders a Container's grid of signal widgets.

``ContainerView`` is the reusable widget that does the actual grid layout. It
can be mounted anywhere (inside a TabPane, a Screen, etc.). ``ContainerScreen``
is a thin Screen wrapper around ContainerView, kept for code that wants to
push the container as its own full-screen view.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import Screen
from textual.widget import Widget

from pgntui.containers.loader import Container
from pgntui.signals.base import AnalogIn, AnalogOut, DigitalIn, DigitalOut, Signal
from pgntui.signals.widgets import (
    AnalogInWidget,
    AnalogOutWidget,
    DigitalInWidget,
    DigitalOutWidget,
)


def _make_widget(sig: Signal, write_enabled: bool) -> Widget:
    if isinstance(sig, AnalogIn):
        return AnalogInWidget(sig)
    if isinstance(sig, AnalogOut):
        return AnalogOutWidget(sig, write_enabled=write_enabled)
    if isinstance(sig, DigitalIn):
        return DigitalInWidget(sig)
    if isinstance(sig, DigitalOut):
        return DigitalOutWidget(sig, write_enabled=write_enabled)
    raise TypeError(f"Unknown signal type: {type(sig).__name__}")


class ContainerView(Widget):
    """Grid view that renders a Container's signal widgets.

    Widgets are exposed via the ``widgets`` dict keyed by ``SignalPlacement.ref``
    so callers can update displayed values or wire write callbacks.
    """

    def __init__(
        self,
        container: Container,
        signals: dict[str, Signal],
        write_enabled: bool,
    ) -> None:
        super().__init__()
        self.container_def = container
        self.signals = signals
        self.write_enabled = write_enabled
        self.widgets: dict[str, Widget] = {}

    def compose(self) -> ComposeResult:
        # Build widgets up front so we can yield them as Grid children.
        # ``column_span`` cannot be assigned before the widget is mounted, so we
        # apply spans in ``on_mount`` once the compose chain has attached us.
        children: list[Widget] = []
        for placement in self.container_def.signals:
            sig = self.signals[placement.ref]
            w = _make_widget(sig, self.write_enabled)
            self.widgets[placement.ref] = w
            children.append(w)
        grid = Grid(*children, id=f"container-grid-{self.container_def.id}")
        grid.styles.grid_size_columns = self.container_def.cols
        yield grid

    def on_mount(self) -> None:
        for placement in self.container_def.signals:
            self.widgets[placement.ref].styles.column_span = placement.w


class ContainerScreen(Screen[None]):
    def __init__(
        self,
        container: Container,
        signals: dict[str, Signal],
        write_enabled: bool,
    ) -> None:
        super().__init__()
        self.container_def = container
        self.signals = signals
        self.write_enabled = write_enabled
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
        )
        yield self._view


__all__ = ["ContainerScreen", "ContainerView"]
