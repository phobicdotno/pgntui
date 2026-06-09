"""Pure sparkline renderers — a list of bucket values -> a glyph string.

No Textual, no theming. ``None`` entries are gaps (rendered as spaces). Analog
auto-scales the visible non-gap values across an 8-level block ramp; digital
renders a step (square) wave. The widget wraps the returned string in themed
Rich ``Text`` and colors it.
"""

from __future__ import annotations

_ANALOG_RAMP = "▁▂▃▄▅▆▇█"  # 8 levels, low -> high
_FLAT = "▄"  # mid glyph for a flat / single-value window
_GAP = " "
_ON = "█"
_OFF = "▁"


def render_analog(cols: list[float | None]) -> str:
    vals = [c for c in cols if c is not None]
    if not vals:
        return _GAP * len(cols)
    lo, hi = min(vals), max(vals)
    span = hi - lo
    top = len(_ANALOG_RAMP) - 1
    out: list[str] = []
    for c in cols:
        if c is None:
            out.append(_GAP)
        elif span == 0:
            out.append(_FLAT)
        else:
            level = round((c - lo) / span * top)
            level = max(0, min(top, level))
            out.append(_ANALOG_RAMP[level])
    return "".join(out)


def render_digital(cols: list[float | None]) -> str:
    out: list[str] = []
    for c in cols:
        if c is None:
            out.append(_GAP)
        elif c >= 0.5:
            out.append(_ON)
        else:
            out.append(_OFF)
    return "".join(out)


def render_analog_rows(cols: list[float | None], rows: int) -> list[str]:
    """Render an analog sparkline ``rows`` text-lines tall (top line first).

    Each column auto-scales across ``rows * 8`` vertical sub-levels (8 per text
    row, the block ramp); a present value always fills at least the bottom 1/8 so
    it never vanishes. ``None`` columns are gaps; a flat window fills to mid
    height. For ``rows <= 1`` this is exactly :func:`render_analog`.
    """
    if rows <= 1:
        return [render_analog(cols)]
    vals = [c for c in cols if c is not None]
    if not vals:
        return [_GAP * len(cols) for _ in range(rows)]
    lo, hi = min(vals), max(vals)
    span = hi - lo
    total = rows * 8  # total sub-levels stacked across all rows
    fills: list[int | None] = []
    for c in cols:
        if c is None:
            fills.append(None)
        elif span == 0:
            fills.append(total // 2)  # flat window -> steady mid-height line
        else:
            f = round((c - lo) / span * total)
            fills.append(max(1, min(total, f)))  # >=1 so a present value shows
    out: list[str] = []
    for i in range(rows):
        rb = rows - 1 - i  # row index counted from the bottom (i=0 is the top)
        line: list[str] = []
        for fill in fills:
            if fill is None:
                line.append(_GAP)
                continue
            eighths = fill - rb * 8
            if eighths <= 0:
                line.append(_GAP)
            elif eighths >= 8:
                line.append("█")
            else:
                line.append(_ANALOG_RAMP[eighths - 1])
        out.append("".join(line))
    return out


def render_digital_rows(cols: list[float | None], rows: int) -> list[str]:
    """Render a digital step-wave ``rows`` text-lines tall (top line first).

    ON fills the full column height; OFF shows the baseline glyph on the bottom
    row only; ``None`` columns are gaps. For ``rows <= 1`` this is exactly
    :func:`render_digital`.
    """
    if rows <= 1:
        return [render_digital(cols)]
    out: list[str] = []
    for i in range(rows):
        rb = rows - 1 - i
        line: list[str] = []
        for c in cols:
            if c is None:
                line.append(_GAP)
            elif c >= 0.5:
                line.append(_ON)
            else:
                line.append(_OFF if rb == 0 else _GAP)
        out.append("".join(line))
    return out


__all__ = ["render_analog", "render_analog_rows", "render_digital", "render_digital_rows"]
