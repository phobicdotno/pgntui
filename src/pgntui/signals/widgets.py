"""Textual signal widgets — AnalogIn, AnalogOut, DigitalIn, DigitalOut."""

from __future__ import annotations

from collections.abc import Callable

from rich.text import Text
from textual.widget import Widget

from pgntui.signals.base import AnalogIn, AnalogOut, DigitalIn, DigitalOut
from pgntui.signals.history import History
from pgntui.signals.sparkline import render_analog, render_digital
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


def _notify_layout(widget: Widget) -> None:
    """Ask the enclosing PageView to resize grid rows for the new expand state.

    Walks up to the first ancestor exposing ``_refresh_grid_rows`` (duck-typed so
    this module needn't import PageView, which would be circular). A no-op for an
    unmounted widget (no parent), so unit tests can toggle freely.
    """
    node = widget.parent
    while node is not None and not hasattr(node, "_refresh_grid_rows"):
        node = node.parent
    if node is not None:
        node._refresh_grid_rows()


class AnalogInWidget(Widget):
    can_focus = True

    def __init__(self, signal: AnalogIn, theme: Theme | None = None, show_bar: bool = True) -> None:
        super().__init__()
        self.signal = signal
        self.theme_def = theme
        # Auto-page numeric rows have no curated min/max, so they hide the bar
        # (show_bar=False) and rely on value + the auto-scaled sparkline.
        self.show_bar = show_bar
        self.displayed_value: float = signal.min
        self._raw: float | None = None
        self.state_class: str = "state-ok"
        # ``False`` until the first reading arrives; drives the diffuse (dimmed)
        # render so a signal that has never reported reads as "no signal".
        self.has_data: bool = False
        # Sparkline state: per-signal time-bucketed history, an expand flag, and
        # the latest clock value the window is rendered against.
        self._history = History()
        self.expanded: bool = False
        self._now: float = 0.0

    def update_value(self, value: float, ts: float | None = None) -> None:
        """Apply ``value`` to the widget and schedule a redraw.

        ``ts`` is the reading's frame timestamp; when given, the displayed value
        is appended to the per-signal history for the sparkline. Legacy callers
        that omit ``ts`` still update the live display but record no history.

        Thread-safety: must be called from the Textual event-loop thread.
        Mutates ``displayed_value`` and ``state_class`` without a lock and then
        calls ``refresh()`` which queues a render message; both are unsafe from
        other threads. From a worker thread (e.g. the frame loop) hop via
        ``App.call_from_thread(widget.update_value, value, ts)``.
        """
        self.has_data = True
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
        if ts is not None:
            self._now = max(self._now, ts)
            # The sparkline is the bar's history, so record the display value.
            self._history.add(self.displayed_value, ts)
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
        return int(self._pct() * (_BAR_WIDTH - 1))

    def _pct(self) -> float:
        span = max(self.signal.max - self.signal.min, 1e-6)
        return max(0.0, min(1.0, (self.displayed_value - self.signal.min) / span))

    def _bar_inner_width(self, value_len: int) -> int:
        """Width of the bar's inner track. Fills the row's remaining space so one
        column ([1]) uses the full width; falls back to the fixed width before the
        widget has been laid out (content_size unknown)."""
        avail = self.content_size.width or 0
        if avail <= 0:
            return _BAR_WIDTH
        # toggle "[+] "(4) + title+space(_TITLE_WIDTH+1) + borders ├┤(2) + space(1) + value
        reserved = 4 + (_TITLE_WIDTH + 1) + 2 + 1 + value_len
        return max(avail - reserved, 6)

    def sparkline_str(self, width: int) -> str:
        """The analog sparkline glyph string for ``width`` columns, rendered
        against the current clock (``_now``)."""
        return render_analog(self._history.columns(self._now, width))

    def toggle_sparkline(self) -> None:
        self.expanded = not self.expanded
        self.set_class(self.expanded, "expanded")
        _notify_layout(self)
        self.refresh(layout=True)  # height switches 1 <-> 2 lines

    def tick(self, now: float) -> None:
        """Advance the render clock so a stopped signal scrolls into gaps."""
        self._now = max(self._now, now)

    def on_click(self) -> None:
        self.focus()
        self.toggle_sparkline()

    def render_text(self) -> str:
        s = self.signal
        unit = f" {s.unit}" if s.unit else ""
        val = f"{self.displayed_value:.{s.decimals}f}"
        tog = "[-]" if self.expanded else "[+]"
        if self.show_bar:
            return f"{tog} {s.title:{_TITLE_WIDTH}s} {self._bar()} {val}{unit}"
        return f"{tog} {s.title:{_TITLE_WIDTH}s} {val}{unit}"

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
        if not self.has_data:
            # No reading yet: render the whole row in the diffuse (dimmed) look
            # so a silent signal is visibly distinct from a live one.
            dim = c["fg_dim"]
            title_style = border_style = track_style = marker_color = value_style = dim
            unit_style = dim
        else:
            state = self.compute_state(self.displayed_value)
            value_color = {"ok": c["fg"], "warn": c["warn"], "alarm": c["alarm"]}[state]
            marker_color = {
                "ok": c["bar_fill"],
                "warn": c["bar_warn"],
                "alarm": c["bar_alarm"],
            }[state]
            title_style = theme.styles.get("title", "") or c["fg"]
            border_style = c["border"]
            track_style = c["bar_track"]
            value_style = f"{theme.styles.get('value', '')} {value_color}".strip()
            unit_style = c["fg_dim"]
        text = Text()
        # A visible, clickable expand toggle so the sparkline is discoverable.
        # Dim with the rest of the row until data arrives (the diffuse look).
        tog_style = c["accent"] if self.has_data else c["fg_dim"]
        text.append("[-] " if self.expanded else "[+] ", style=tog_style)
        text.append(f"{s.title:{_TITLE_WIDTH}s} ", style=title_style)
        val = f"{self.displayed_value:.{s.decimals}f}"
        unit = f" {s.unit}" if s.unit else ""
        if self.show_bar:
            inner = self._bar_inner_width(len(val) + len(unit))
            marker_at = int(self._pct() * (inner - 1))
            text.append(_glyph(theme, "bar_left"), style=border_style)
            for i in range(inner):
                glyph = "bar_marker" if i == marker_at else "bar_track"
                text.append(
                    _glyph(theme, glyph), style=marker_color if i == marker_at else track_style
                )
            text.append(_glyph(theme, "bar_right"), style=border_style)
        text.append(f" {val}", style=value_style)
        if s.unit:
            text.append(f" {s.unit}", style=unit_style)
        if self.expanded:
            width = max((self.content_size.width or 0) - 2, 0)
            spark = self.sparkline_str(width) if width >= 4 else ""
            if spark:
                # Crop the signal line to exactly one cell-width so it can't wrap
                # and shove the sparkline onto a clipped third line in a narrow
                # multi-column cell.
                text.truncate(self.content_size.width, overflow="crop")
                text.append("\n  ")
                text.append(spark, style=c["bar_fill"])
        return text

    def clear(self) -> None:
        """Reset to the no-data (diffuse) state.

        Used when the page switches NMEA instance so the previous instance's
        readings don't linger as if they were the new instance's data. The
        sparkline history is a different data series per instance, so it is
        cleared too; the expand flag is kept so the row stays open and refills
        from gaps.
        """
        self.has_data = False
        self._raw = None
        self.displayed_value = self.signal.min
        self.state_class = "state-ok"
        self._history.clear()
        # Reset the render clock to the initial state too, so the next
        # instance's readings anchor the window at their own timestamps rather
        # than a stale clock left over from the previous instance.
        self._now = 0.0
        self.refresh()


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
        # 4-space indent to line up with the [+] prefix on input rows.
        return f"    {s.title:{_TITLE_WIDTH}s} {val}{unit} {tail}"

    def render(self) -> Text | str:
        theme = self.theme_def
        if theme is None:
            return self.render_text()
        c = theme.colors
        s = self.signal
        text = Text()
        text.append("    ")  # align with the [+] indent on input rows
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
    can_focus = True

    def __init__(self, signal: DigitalIn, theme: Theme | None = None) -> None:
        super().__init__()
        self.signal = signal
        self.theme_def = theme
        self.value: bool = False
        # ``False`` until the first reading arrives — see AnalogInWidget.has_data.
        self.has_data: bool = False
        self._history = History()
        self.expanded: bool = False
        self._now: float = 0.0

    def update_value(self, value: object, ts: float | None = None) -> None:
        self.has_data = True
        if self.signal.bit is not None:
            self.value = bool((int(value) >> self.signal.bit) & 1)  # type: ignore[call-overload]
        else:
            self.value = bool(value)
        if ts is not None:
            self._now = max(self._now, ts)
            self._history.add(1.0 if self.value else 0.0, ts)
        self.refresh()

    def sparkline_str(self, width: int) -> str:
        """The digital step-wave glyph string for ``width`` columns."""
        return render_digital(self._history.columns(self._now, width))

    def toggle_sparkline(self) -> None:
        self.expanded = not self.expanded
        self.set_class(self.expanded, "expanded")
        _notify_layout(self)
        self.refresh(layout=True)

    def tick(self, now: float) -> None:
        self._now = max(self._now, now)

    def on_click(self) -> None:
        self.focus()
        self.toggle_sparkline()

    def render_text(self) -> str:
        s = self.signal
        glyph = _glyph(self.theme_def, "on" if self.value else "off")
        label = s.on_label if self.value else s.off_label
        tog = "[-]" if self.expanded else "[+]"
        return f"{tog} {s.title:{_TITLE_WIDTH}s} {glyph} {label}"

    def render(self) -> Text | str:
        theme = self.theme_def
        if theme is None:
            return self.render_text()
        c = theme.colors
        s = self.signal
        # No reading yet: dim the title too, so a silent input is distinct from a
        # live input that happens to read OFF (which keeps a bright title).
        if not self.has_data:
            title_style = c["fg_dim"]
        else:
            title_style = theme.styles.get("title", "") or c["fg"]
        text = Text()
        # A visible, clickable expand toggle so the sparkline is discoverable.
        # Dim with the rest of the row until data arrives (the diffuse look).
        tog_style = c["accent"] if self.has_data else c["fg_dim"]
        text.append("[-] " if self.expanded else "[+] ", style=tog_style)
        text.append(f"{s.title:{_TITLE_WIDTH}s} ", style=title_style)
        if self.value:
            text.append(_glyph(theme, "on"), style=c["ok"])
            text.append(f" {s.on_label}", style=c["fg"])
        else:
            text.append(_glyph(theme, "off"), style=c["fg_dim"])
            text.append(f" {s.off_label}", style=c["fg_dim"])
        if self.expanded:
            width = max((self.content_size.width or 0) - 2, 0)
            spark = self.sparkline_str(width) if width >= 4 else ""
            if spark:
                # Crop to one cell-width so the sparkline stays line two even in
                # a narrow multi-column cell.
                text.truncate(self.content_size.width, overflow="crop")
                text.append("\n  ")
                text.append(spark, style=c["bar_fill"])
        return text

    def clear(self) -> None:
        """Reset to the no-data (diffuse) state on instance switch."""
        self.has_data = False
        self.value = False
        self._history.clear()
        # Reset the render clock too (see AnalogInWidget.clear) so a new
        # instance's readings anchor the window at their own timestamps.
        self._now = 0.0
        self.refresh()


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
        # 4-space indent to line up with the [+] prefix on input rows.
        return f"    {s.title:{_TITLE_WIDTH}s} [{glyph} {label}]"

    def render(self) -> Text | str:
        theme = self.theme_def
        if theme is None:
            return self.render_text()
        c = theme.colors
        s = self.signal
        body_color = c["fg"] if self.write_enabled else c["fg_dim"]
        text = Text()
        text.append("    ")  # align with the [+] indent on input rows
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


class AutoTextWidget(Widget):
    """A read-only Auto-page row for a non-numeric field: ``title  value``.

    No bar, no sparkline, not focusable. Indented 4 to line up with the [+] on
    numeric Auto rows. ``set_text`` pushes the latest decoded value.
    """

    def __init__(self, title: str, theme: Theme | None = None) -> None:
        super().__init__()
        self.title = title
        self.theme_def = theme
        self._text = ""

    def set_text(self, text: str) -> None:
        self._text = text
        self.refresh()

    def render(self) -> Text | str:
        theme = self.theme_def
        if theme is None:
            return f"    {self.title:{_TITLE_WIDTH}s} {self._text}"
        c = theme.colors
        text = Text()
        text.append("    ")  # align with the [+] indent on numeric rows
        text.append(
            f"{self.title:{_TITLE_WIDTH}s} ", style=theme.styles.get("title", "") or c["fg"]
        )
        text.append(self._text, style=c["fg"])
        return text
