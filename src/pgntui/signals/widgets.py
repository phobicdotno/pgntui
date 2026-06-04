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


class AnalogOutWidget(Widget):
    def __init__(self, signal: AnalogOut, write_enabled: bool = False) -> None:
        super().__init__()
        self.signal = signal
        self.write_enabled = write_enabled
        self.value: float = signal.min
        self.on_write = None  # type: ignore[assignment]

    @property
    def is_disabled(self) -> bool:
        return not self.write_enabled

    def submit_set(self, value: float) -> None:
        if not self.write_enabled:
            return
        self.value = float(value)
        if callable(self.on_write):
            self.on_write(self.value)
        self.refresh()

    def render_text(self) -> str:
        s = self.signal
        unit = f" {s.unit}" if s.unit else ""
        val = f"{self.value:.{s.decimals}f}"
        tail = "[set]" if self.write_enabled else "[disabled]"
        return f"{s.title:20s} {val}{unit} {tail}"

    def render(self):
        return self.render_text()


class DigitalInWidget(Widget):
    def __init__(self, signal: DigitalIn) -> None:
        super().__init__()
        self.signal = signal
        self.value: bool = False

    def update_value(self, value: bool) -> None:
        self.value = bool(value)
        self.refresh()

    def render_text(self) -> str:
        s = self.signal
        glyph = "●" if self.value else "○"
        label = s.on_label if self.value else s.off_label
        return f"{s.title:20s} {glyph} {label}"

    def render(self):
        return self.render_text()


class DigitalOutWidget(Widget):
    def __init__(self, signal: DigitalOut, write_enabled: bool = False) -> None:
        super().__init__()
        self.signal = signal
        self.write_enabled = write_enabled
        self.value: bool = False
        self.on_write = None  # type: ignore[assignment]

    @property
    def is_disabled(self) -> bool:
        return not self.write_enabled

    def toggle(self) -> None:
        if not self.write_enabled:
            return
        self.value = not self.value
        if callable(self.on_write):
            self.on_write(self.value)
        self.refresh()

    def render_text(self) -> str:
        s = self.signal
        glyph = "●" if self.value else "○"
        label = s.on_label if self.value else s.off_label
        return f"{s.title:20s} [{glyph} {label}]"

    def render(self):
        return self.render_text()
