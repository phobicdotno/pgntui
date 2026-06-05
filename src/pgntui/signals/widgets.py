"""Textual signal widgets — AnalogIn, AnalogOut, DigitalIn, DigitalOut."""

from __future__ import annotations

from collections.abc import Callable

from rich.text import Text
from textual.widget import Widget

from pgntui.signals.base import AnalogIn, AnalogOut, DigitalIn, DigitalOut
from pgntui.themes.loader import Theme

_BAR_WIDTH = 18
_TITLE_WIDTH = 20

# Fallback glyphs when the theme defines none (or no theme is set).
_DEFAULT_GLYPHS = {
    "bar_left": "├",
    "bar_right": "┤",
    "bar_track": "─",
    "bar_marker": "●",
    "on": "●",
    "off": "○",
}


def _glyph(theme: Theme | None, key: str) -> str:
    if theme is not None and key in theme.glyphs:
        return theme.glyphs[key]
    return _DEFAULT_GLYPHS[key]


class AnalogInWidget(Widget):
    def __init__(self, signal: AnalogIn, theme: Theme | None = None) -> None:
        super().__init__()
        self.signal = signal
        self.theme_def = theme
        self.displayed_value: float = signal.min
        self._raw: float | None = None
        self.state_class: str = "state-ok"

    def update_value(self, value: float) -> None:
        """Apply ``value`` to the widget and schedule a redraw.

        Thread-safety: must be called from the Textual event-loop thread.
        Mutates ``displayed_value`` and ``state_class`` without a lock and then
        calls ``refresh()`` which queues a render message; both are unsafe from
        other threads. From a worker thread (e.g. the frame loop) hop via
        ``App.call_from_thread(widget.update_value, value)``.
        """
        # Convert decoded (SI) value into display units before smoothing so
        # min/max, thresholds, and the bar all operate in display units.
        value = float(value) * self.signal.scale + self.signal.offset
        if self.signal.smoothing > 0 and self._raw is not None:
            a = self.signal.smoothing
            self.displayed_value = a * self._raw + (1 - a) * value
        else:
            self.displayed_value = float(value)
        self._raw = float(value)
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

    def _marker_at(self) -> int:
        span = max(self.signal.max - self.signal.min, 1e-6)
        pct = (self.displayed_value - self.signal.min) / span
        pct = max(0.0, min(1.0, pct))
        return int(pct * (_BAR_WIDTH - 1))

    def render_text(self) -> str:
        s = self.signal
        unit = f" {s.unit}" if s.unit else ""
        val = f"{self.displayed_value:.{s.decimals}f}"
        bar = self._bar()
        return f"{s.title:{_TITLE_WIDTH}s} {bar} {val}{unit}"

    def _bar(self) -> str:
        marker_at = self._marker_at()
        left = _glyph(self.theme_def, "bar_left")
        right = _glyph(self.theme_def, "bar_right")
        track = _glyph(self.theme_def, "bar_track")
        marker = _glyph(self.theme_def, "bar_marker")
        inner = "".join(marker if i == marker_at else track for i in range(_BAR_WIDTH))
        return f"{left}{inner}{right}"

    def render(self) -> Text | str:
        theme = self.theme_def
        if theme is None:
            return self.render_text()
        c = theme.colors
        s = self.signal
        state = self.compute_state(self.displayed_value)
        value_color = {"ok": c["fg"], "warn": c["warn"], "alarm": c["alarm"]}[state]
        marker_color = {"ok": c["bar_fill"], "warn": c["bar_warn"], "alarm": c["bar_alarm"]}[state]
        marker_at = self._marker_at()
        track_style = c["bar_track"]
        text = Text()
        text.append(f"{s.title:{_TITLE_WIDTH}s} ", style=theme.styles.get("title", "") or c["fg"])
        text.append(_glyph(theme, "bar_left"), style=c["border"])
        for i in range(_BAR_WIDTH):
            if i == marker_at:
                text.append(_glyph(theme, "bar_marker"), style=marker_color)
            else:
                text.append(_glyph(theme, "bar_track"), style=track_style)
        text.append(_glyph(theme, "bar_right"), style=c["border"])
        val = f"{self.displayed_value:.{s.decimals}f}"
        value_style = f"{theme.styles.get('value', '')} {value_color}".strip()
        text.append(f" {val}", style=value_style)
        if s.unit:
            text.append(f" {s.unit}", style=c["fg_dim"])
        return text


class AnalogOutWidget(Widget):
    def __init__(
        self, signal: AnalogOut, write_enabled: bool = False, theme: Theme | None = None
    ) -> None:
        super().__init__()
        self.signal = signal
        self.theme_def = theme
        self.write_enabled = write_enabled
        self.value: float = signal.min
        self.on_write: Callable[[float], None] | None = None

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
        return f"{s.title:{_TITLE_WIDTH}s} {val}{unit} {tail}"

    def render(self) -> Text | str:
        theme = self.theme_def
        if theme is None:
            return self.render_text()
        c = theme.colors
        s = self.signal
        text = Text()
        text.append(f"{s.title:{_TITLE_WIDTH}s} ", style=theme.styles.get("title", "") or c["fg"])
        val = f"{self.value:.{s.decimals}f}"
        text.append(val, style=f"{theme.styles.get('value', '')} {c['accent']}".strip())
        if s.unit:
            text.append(f" {s.unit}", style=c["fg_dim"])
        if self.write_enabled:
            text.append(" [set]", style=c["accent"])
        else:
            text.append(" [disabled]", style=c["fg_dim"])
        return text


class DigitalInWidget(Widget):
    def __init__(self, signal: DigitalIn, theme: Theme | None = None) -> None:
        super().__init__()
        self.signal = signal
        self.theme_def = theme
        self.value: bool = False

    def update_value(self, value: object) -> None:
        if self.signal.bit is not None:
            self.value = bool((int(value) >> self.signal.bit) & 1)  # type: ignore[call-overload]
        else:
            self.value = bool(value)
        self.refresh()

    def render_text(self) -> str:
        s = self.signal
        glyph = _glyph(self.theme_def, "on" if self.value else "off")
        label = s.on_label if self.value else s.off_label
        return f"{s.title:{_TITLE_WIDTH}s} {glyph} {label}"

    def render(self) -> Text | str:
        theme = self.theme_def
        if theme is None:
            return self.render_text()
        c = theme.colors
        s = self.signal
        text = Text()
        text.append(f"{s.title:{_TITLE_WIDTH}s} ", style=theme.styles.get("title", "") or c["fg"])
        if self.value:
            text.append(_glyph(theme, "on"), style=c["ok"])
            text.append(f" {s.on_label}", style=c["fg"])
        else:
            text.append(_glyph(theme, "off"), style=c["fg_dim"])
            text.append(f" {s.off_label}", style=c["fg_dim"])
        return text


class DigitalOutWidget(Widget):
    def __init__(
        self, signal: DigitalOut, write_enabled: bool = False, theme: Theme | None = None
    ) -> None:
        super().__init__()
        self.signal = signal
        self.theme_def = theme
        self.write_enabled = write_enabled
        self.value: bool = False
        self.on_write: Callable[[bool], None] | None = None

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
        glyph = _glyph(self.theme_def, "on" if self.value else "off")
        label = s.on_label if self.value else s.off_label
        return f"{s.title:{_TITLE_WIDTH}s} [{glyph} {label}]"

    def render(self) -> Text | str:
        theme = self.theme_def
        if theme is None:
            return self.render_text()
        c = theme.colors
        s = self.signal
        body_color = c["fg"] if self.write_enabled else c["fg_dim"]
        text = Text()
        text.append(f"{s.title:{_TITLE_WIDTH}s} ", style=theme.styles.get("title", "") or c["fg"])
        text.append("[", style=c["border"])
        if self.value:
            text.append(_glyph(theme, "on"), style=c["ok"] if self.write_enabled else c["fg_dim"])
            text.append(f" {s.on_label}", style=body_color)
        else:
            text.append(_glyph(theme, "off"), style=c["fg_dim"])
            text.append(f" {s.off_label}", style=body_color)
        text.append("]", style=c["border"])
        return text
