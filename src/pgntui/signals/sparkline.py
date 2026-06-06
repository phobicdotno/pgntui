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


__all__ = ["render_analog", "render_digital"]
