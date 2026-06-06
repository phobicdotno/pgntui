"""AutoPageBuilder — fills the Auto page from the live decoded-frame stream.

Every ``(pgn, source)`` seen becomes one titled container; each decoded field is
a row: numeric fields render as an ``AnalogInWidget`` without a bar (value + the
on-demand sparkline), non-numeric fields as a read-only ``AutoTextWidget``.
Containers are built first-seen on the UI thread (capped), then updated in place.

See docs/superpowers/specs/2026-06-06-auto-page-design.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widget import Widget

from pgntui.decode.canboat import DecodedFrame
from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget, AutoTextWidget
from pgntui.themes.loader import Theme

if TYPE_CHECKING:
    from pgntui.pages.view import PageView


def _is_numeric(value: object) -> bool:
    """A field value we can show as a numeric row (and sparkline)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class AutoPageBuilder:
    def __init__(
        self, view: PageView, *, theme: Theme | None = None, max_containers: int = 50
    ) -> None:
        self._view = view
        self._theme = theme
        self._max = max_containers
        # (pgn, source) -> {field_name: row widget}, in build order.
        self._rows: dict[tuple[int, int], dict[str, Widget]] = {}

    @property
    def at_capacity(self) -> bool:
        return len(self._rows) >= self._max

    @property
    def count(self) -> int:
        return len(self._rows)

    def ingest(self, decoded: DecodedFrame) -> None:
        """Create a container for a new ``(pgn, source)`` (up to the cap), then
        push the frame's field values into that container's rows. Runs on the
        Textual event-loop thread (hop via ``call_from_thread``)."""
        key = (decoded.pgn, decoded.source_addr)
        rows = self._rows.get(key)
        if rows is None:
            if self.at_capacity:
                return
            rows = self._build(decoded)
            self._rows[key] = rows
        ts = decoded.timestamp
        for name, widget in rows.items():
            if name not in decoded.fields:
                continue
            value = decoded.fields[name]
            if isinstance(widget, AnalogInWidget):
                if _is_numeric(value):
                    widget.update_value(float(value), ts)
            elif isinstance(widget, AutoTextWidget):
                widget.set_text(str(value))

    def _build(self, decoded: DecodedFrame) -> dict[str, Widget]:
        rows: dict[str, Widget] = {}
        ordered: list[Widget] = []
        for name, value in decoded.fields.items():
            widget: Widget
            if _is_numeric(value):
                sig = AnalogIn(
                    id=f"auto-{decoded.pgn}-{decoded.source_addr}-{name}",
                    type="analog_in",
                    title=name,
                    pgn=decoded.pgn,
                    field=name,
                )
                widget = AnalogInWidget(sig, theme=self._theme, show_bar=False)
            else:
                widget = AutoTextWidget(name, theme=self._theme)
            rows[name] = widget
            ordered.append(widget)
        name = decoded.name or ""
        title = (
            f"{decoded.pgn} {name} · src {decoded.source_addr}"
            if name
            else f"{decoded.pgn} · src {decoded.source_addr}"
        )
        self._view.add_generated_container(title, ordered)
        return rows


__all__ = ["AutoPageBuilder"]
