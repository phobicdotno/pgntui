"""AutoPageBuilder — fills the Auto page from the live decoded-frame stream.

Every ``(pgn, source, instance)`` seen becomes one titled container; each decoded
field is a row: numeric fields render as an ``AnalogInWidget`` without a bar
(value + the on-demand sparkline), non-numeric fields as a read-only
``AutoTextWidget``. A PGN that reports several Instances from one source (e.g.
several engines) gets one box per instance. Containers are built first-seen on
the UI thread (capped), then updated in place.

See docs/superpowers/specs/2026-06-06-auto-page-design.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widget import Widget

from pgntui.decode.canboat import CanboatDecoder, DecodedFrame, frame_instance
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
        self,
        view: PageView,
        *,
        theme: Theme | None = None,
        max_containers: int = 50,
        decoder: CanboatDecoder | None = None,
    ) -> None:
        self._view = view
        self._theme = theme
        self._max = max_containers
        # Used to label numeric rows with the field's canboat SI unit.
        self._decoder = decoder
        # (pgn, source, instance) -> {field_name: row widget}, in build order.
        # ``instance`` is None for PGNs without an Instance field.
        self._rows: dict[tuple[int, int, int | None], dict[str, Widget]] = {}

    def reset(self) -> None:
        """Forget all built containers — used before a masonry column rebuild, so
        re-ingesting from the buffer creates fresh boxes in the new columns."""
        self._rows = {}

    @property
    def at_capacity(self) -> bool:
        return len(self._rows) >= self._max

    @property
    def count(self) -> int:
        return len(self._rows)

    def ingest(self, decoded: DecodedFrame) -> None:
        """Create a container for a new ``(pgn, source, instance)`` (up to the
        cap), then push the frame's field values into that container's rows. Runs
        on the Textual event-loop thread (hop via ``call_from_thread``)."""
        instance = frame_instance(decoded)
        key = (decoded.pgn, decoded.source_addr, instance)
        rows = self._rows.get(key)
        if rows is None:
            if self.at_capacity:
                return
            rows = self._build(decoded, instance)
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

    def _build(self, decoded: DecodedFrame, instance: int | None) -> dict[str, Widget]:
        rows: dict[str, Widget] = {}
        ordered: list[Widget] = []
        inst_tag = "" if instance is None else f"-i{instance}"
        for name, value in decoded.fields.items():
            widget: Widget
            if _is_numeric(value):
                unit = self._decoder.field_unit(decoded.pgn, name) if self._decoder else None
                sig = AnalogIn(
                    # inst_tag keeps ids unique across instances of one PGN/source.
                    id=f"auto-{decoded.pgn}-{decoded.source_addr}{inst_tag}-{name}",
                    type="analog_in",
                    title=name,
                    pgn=decoded.pgn,
                    field=name,
                    unit=unit,
                )
                widget = AnalogInWidget(sig, theme=self._theme, show_bar=False)
            else:
                widget = AutoTextWidget(name, theme=self._theme)
            rows[name] = widget
            ordered.append(widget)
        name = decoded.name or ""
        title = f"{decoded.pgn} {name} · src {decoded.source_addr}".replace("  ", " ")
        if not name:
            title = f"{decoded.pgn} · src {decoded.source_addr}"
        if instance is not None:
            title = f"{title} · Instance {instance}"
        self._view.add_generated_container(title, ordered)
        return rows


__all__ = ["AutoPageBuilder"]
