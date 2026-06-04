"""Textual signal widgets — AnalogIn, AnalogOut, DigitalIn, DigitalOut."""

from __future__ import annotations

from textual.widget import Widget

from pgntui.signals.base import AnalogIn, AnalogOut, DigitalIn, DigitalOut


class AnalogInWidget(Widget):
    def __init__(self, signal: AnalogIn) -> None:
        super().__init__()
        self.signal = signal
        self.displayed_value: float = signal.min
        self._raw: float | None = None
        self.state_class: str = "state-ok"

    def update_value(self, value: float) -> None:
        if self.signal.smoothing > 0 and self._raw is not None:
            a = self.signal.smoothing
            self.displayed_value = a * self._raw + (1 - a) * value
        else:
            self.displayed_value = float(value)
        self._raw = self.displayed_value
        self.state_class = f"state-{self.compute_state(self.displayed_value)}"
        self.refresh()

    def compute_state(self, v: float) -> str:
        s = self.signal
        if s.alarm_above is not None and v >= s.alarm_above:
            return "alarm"
        if s.warn_above is not None and v >= s.warn_above:
            return "warn"
        if s.alarm_below is not None and v <= s.alarm_below:
            return "alarm"
        if s.warn_below is not None and v <= s.warn_below:
            return "warn"
        return "ok"

    def render_text(self) -> str:
        s = self.signal
        unit = f" {s.unit}" if s.unit else ""
        val = f"{self.displayed_value:.{s.decimals}f}"
        bar = self._bar()
        return f"{s.title:20s} {bar} {val}{unit}"

    def _bar(self) -> str:
        width = 18
        span = max(self.signal.max - self.signal.min, 1e-6)
        pct = (self.displayed_value - self.signal.min) / span
        pct = max(0.0, min(1.0, pct))
        marker_at = int(pct * (width - 1))
        inner = "".join("●" if i == marker_at else "─" for i in range(width))
        return f"├{inner}┤"

    def render(self):
        return self.render_text()
