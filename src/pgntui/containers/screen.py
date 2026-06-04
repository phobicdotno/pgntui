"""ContainerScreen — renders a Container's grid of signal widgets."""

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
        self.widgets: dict[str, Widget] = {}

    def compose(self) -> ComposeResult:
        grid = Grid(id="container-grid")
        grid.styles.grid_size_columns = self.container_def.cols
        for placement in self.container_def.signals:
            sig = self.signals[placement.ref]
            w = self._make_widget(sig)
            w.styles.column_span = placement.w
            self.widgets[placement.ref] = w
        yield grid

    def on_mount(self) -> None:
        grid = self.query_one(Grid)
        for w in self.widgets.values():
            grid.mount(w)

    def _make_widget(self, sig: Signal) -> Widget:
        if isinstance(sig, AnalogIn):
            return AnalogInWidget(sig)
        if isinstance(sig, AnalogOut):
            return AnalogOutWidget(sig, write_enabled=self.write_enabled)
        if isinstance(sig, DigitalIn):
            return DigitalInWidget(sig)
        if isinstance(sig, DigitalOut):
            return DigitalOutWidget(sig, write_enabled=self.write_enabled)
        raise TypeError(f"Unknown signal type: {type(sig).__name__}")


__all__ = ["ContainerScreen"]
