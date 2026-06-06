# Sparklines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reveal a per-signal, time-bucketed historical sparkline under any input signal row, toggled by keyboard (cursor + `+`) or mouse click.

**Architecture:** A pure `History` class (time-bucketed samples) and pure `sparkline` render functions are composed into `AnalogInWidget`/`DigitalInWidget`. Each input widget owns a `History`, captures every reading with its timestamp, and renders an optional second line when expanded. The app forwards the already-present `SignalUpdate.timestamp`, keeps a shared clock from the latest frame, and runs a 1 s repaint timer so a stopped signal scrolls into trailing gaps. Selection uses native Textual focus.

**Tech Stack:** Python 3.11, Textual 8.2, Rich, pytest (`pytest-asyncio`), ruff, mypy. Spec: `docs/superpowers/specs/2026-06-06-sparklines-design.md`.

**Conventions (from the repo):**
- Run tests: `.venv\Scripts\python.exe -m pytest -q` (a single test: `... -m pytest tests/test_x.py::test_y -v`).
- Lint/type: `.venv\Scripts\python.exe -m ruff check src tests` · `... -m ruff format src tests` · `... -m mypy src`.
- Commit AND push every working change to `main`. **No AI attribution** in commits or code.
- Source files may use UTF-8 block glyphs (the TUI renders them); keep them out of `print()` to a cp1252 console only.

---

## File Structure

**Create:**
- `src/pgntui/signals/history.py` — `History`: time-bucketed sample store (pure data).
- `src/pgntui/signals/sparkline.py` — `render_analog`, `render_digital` (pure glyph renderers).
- `tests/test_history.py` — unit tests for `History`.
- `tests/test_sparkline.py` — unit tests for the renderers.
- `tests/test_widgets_sparkline.py` — widget-level capture/expand/focus tests.
- `tests/test_app_sparkline.py` — pilot tests for clock, bindings, focus movement.

**Modify:**
- `src/pgntui/signals/widgets.py` — `AnalogInWidget` + `DigitalInWidget`: own a `History`, `update_value(value, ts=None)`, `expanded`/`toggle_sparkline`/`tick`/`sparkline_str`, `can_focus`, `on_click`, `clear()` clears history.
- `src/pgntui/pages/view.py` — CSS: `grid-rows: auto`, input widgets `height: auto`, `:focus` highlight.
- `src/pgntui/app.py` — `_clock`, forward timestamp into `_apply_update`, repaint timer, `+`/`up`/`down` bindings + actions.
- `src/pgntui/__init__.py`, `pyproject.toml`, `src/pgntui/about.py` — version 0.3.13 → 0.4.0 + release note.

---

## Task 1: `History` — time-bucketed sample store

**Files:**
- Create: `src/pgntui/signals/history.py`
- Test: `tests/test_history.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_history.py
from pgntui.signals.history import History


def test_add_buckets_by_timestamp_last_wins() -> None:
    h = History(bucket_seconds=1.0, capacity=10)
    h.add(1.0, ts=0.1)
    h.add(2.0, ts=0.9)  # same 1 s bucket as 0.1 -> overwrites
    h.add(5.0, ts=1.2)  # next bucket
    assert h.columns(now=1.2, width=2) == [2.0, 5.0]


def test_columns_right_edge_is_now_and_gaps_are_none() -> None:
    h = History(bucket_seconds=1.0, capacity=10)
    h.add(3.0, ts=0.0)   # bucket 0
    h.add(7.0, ts=2.0)   # bucket 2  (bucket 1 never written -> gap)
    # window of 3 ending at now=2.x -> buckets 0,1,2
    assert h.columns(now=2.5, width=3) == [3.0, None, 7.0]
    # advance now with no new data: signal scrolls left into trailing gaps
    assert h.columns(now=4.5, width=3) == [7.0, None, None]


def test_columns_zero_or_negative_width() -> None:
    h = History()
    assert h.columns(now=0.0, width=0) == []


def test_eviction_drops_oldest_beyond_capacity() -> None:
    h = History(bucket_seconds=1.0, capacity=3)
    for i in range(5):
        h.add(float(i), ts=float(i))  # buckets 0..4
    assert len(h) == 3
    # only buckets 2,3,4 survive
    assert h.columns(now=4.0, width=5) == [None, None, 2.0, 3.0, 4.0]


def test_clear_empties() -> None:
    h = History()
    h.add(1.0, ts=0.0)
    h.clear()
    assert len(h) == 0
    assert h.columns(now=0.0, width=2) == [None, None]


def test_rejects_bad_params() -> None:
    import pytest

    with pytest.raises(ValueError):
        History(bucket_seconds=0)
    with pytest.raises(ValueError):
        History(capacity=0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_history.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pgntui.signals.history'`.

- [ ] **Step 3: Implement `History`**

```python
# src/pgntui/signals/history.py
"""Time-bucketed sample history for sparklines.

Pure data — no Textual, no glyphs — so it unit-tests in isolation. Each sample
is assigned to a fixed wall-clock bucket (``int(ts // bucket_seconds)``); the
last value written to a bucket wins. ``columns`` projects the stored buckets
onto a fixed-width window ending at "now", with ``None`` for buckets that never
received a sample (gaps), so a stopped signal scrolls left into trailing gaps.
"""

from __future__ import annotations


class History:
    def __init__(self, bucket_seconds: float = 1.0, capacity: int = 300) -> None:
        if bucket_seconds <= 0:
            raise ValueError("bucket_seconds must be > 0")
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.bucket_seconds = bucket_seconds
        self.capacity = capacity
        # Insertion-ordered (dict preserves order); key = bucket index, value =
        # last sample in that bucket. Re-writing a key keeps its position, so the
        # front is always the oldest bucket.
        self._buckets: dict[int, float] = {}

    def add(self, value: float, ts: float) -> None:
        idx = int(ts // self.bucket_seconds)
        self._buckets[idx] = float(value)
        while len(self._buckets) > self.capacity:
            oldest = next(iter(self._buckets))
            del self._buckets[oldest]

    def columns(self, now: float, width: int) -> list[float | None]:
        if width <= 0:
            return []
        now_idx = int(now // self.bucket_seconds)
        start = now_idx - (width - 1)
        return [self._buckets.get(start + i) for i in range(width)]

    def clear(self) -> None:
        self._buckets.clear()

    def __len__(self) -> int:
        return len(self._buckets)


__all__ = ["History"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_history.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit & push**

```bash
git add src/pgntui/signals/history.py tests/test_history.py
git commit -m "feat(history): time-bucketed sample store for sparklines"
git push origin main
```

---

## Task 2: `sparkline` — pure glyph renderers

**Files:**
- Create: `src/pgntui/signals/sparkline.py`
- Test: `tests/test_sparkline.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sparkline.py
from pgntui.signals.sparkline import render_analog, render_digital

RAMP = "▁▂▃▄▅▆▇█"


def test_analog_maps_low_and_high_to_ramp_ends() -> None:
    out = render_analog([0.0, 10.0])
    assert out[0] == RAMP[0]   # lowest -> ▁
    assert out[-1] == RAMP[-1]  # highest -> █


def test_analog_autoscales_to_window() -> None:
    # A narrow band 80..90 should still use the full ramp.
    out = render_analog([80.0, 82.5, 85.0, 87.5, 90.0])
    assert out[0] == RAMP[0]
    assert out[-1] == RAMP[-1]
    assert set(out) - set(RAMP) == set()  # only ramp glyphs


def test_analog_flat_window_is_mid_glyph() -> None:
    assert render_analog([5.0, 5.0, 5.0]) == "▄▄▄"


def test_analog_gaps_render_as_spaces() -> None:
    out = render_analog([0.0, None, 10.0])
    assert out == f"{RAMP[0]} {RAMP[-1]}"


def test_analog_all_gaps_is_blank() -> None:
    assert render_analog([None, None, None]) == "   "


def test_digital_steps_and_gaps() -> None:
    assert render_digital([0.0, 1.0, 1.0, 0.0, None]) == "▁██▁ "


def test_digital_threshold_at_half() -> None:
    assert render_digital([0.49, 0.5]) == "▁█"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sparkline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pgntui.signals.sparkline'`.

- [ ] **Step 3: Implement the renderers**

```python
# src/pgntui/signals/sparkline.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sparkline.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit & push**

```bash
git add src/pgntui/signals/sparkline.py tests/test_sparkline.py
git commit -m "feat(sparkline): pure analog/digital glyph renderers"
git push origin main
```

---

## Task 3: `AnalogInWidget` — capture history, expand, focus

**Files:**
- Modify: `src/pgntui/signals/widgets.py` (`AnalogInWidget`, lines ~33-152; module imports at top)
- Test: `tests/test_widgets_sparkline.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_widgets_sparkline.py
from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget


def _sig(**kw) -> AnalogIn:
    base = dict(id="rpm", type="analog_in", title="RPM", pgn=127488,
                field="Engine Speed", unit="rpm", min=0.0, max=6000.0, smoothing=0.0)
    base.update(kw)
    return AnalogIn(**base)


def test_update_value_with_ts_feeds_history() -> None:
    w = AnalogInWidget(_sig())
    w.update_value(1000.0, ts=0.0)
    w.update_value(2000.0, ts=1.0)
    # displayed_value is captured (display units), newest at the right edge
    assert w.sparkline_str(2) == "▁█"


def test_update_value_without_ts_does_not_capture() -> None:
    w = AnalogInWidget(_sig())
    w.update_value(1000.0)  # legacy call path (no ts) -> no history
    assert w.sparkline_str(3) == "   "


def test_toggle_sparkline_flips_expanded() -> None:
    w = AnalogInWidget(_sig())
    assert w.expanded is False
    w.toggle_sparkline()
    assert w.expanded is True
    w.toggle_sparkline()
    assert w.expanded is False


def test_tick_advances_window_into_gaps() -> None:
    w = AnalogInWidget(_sig())
    w.update_value(3000.0, ts=0.0)
    assert w.sparkline_str(3)[-1] != " "  # data at the right edge
    w.tick(5.0)  # 5 s later, no new data
    assert w.sparkline_str(3) == "█  "  # scrolled left, trailing gaps


def test_clear_empties_history_keeps_expanded() -> None:
    w = AnalogInWidget(_sig())
    w.update_value(1000.0, ts=0.0)
    w.toggle_sparkline()
    w.clear()
    assert w.expanded is True
    assert w.sparkline_str(2) == "  "


def test_is_focusable() -> None:
    assert AnalogInWidget(_sig()).can_focus is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_widgets_sparkline.py -v`
Expected: FAIL — `AttributeError` (`sparkline_str` / `expanded` / `toggle_sparkline` / `tick` not defined; `can_focus` is False).

- [ ] **Step 3: Add imports at the top of `widgets.py`**

Find (lines ~10-11):

```python
from pgntui.signals.base import AnalogIn, AnalogOut, DigitalIn, DigitalOut
from pgntui.themes.loader import Theme
```

Replace with:

```python
from pgntui.signals.base import AnalogIn, AnalogOut, DigitalIn, DigitalOut
from pgntui.signals.history import History
from pgntui.signals.sparkline import render_analog, render_digital
from pgntui.themes.loader import Theme
```

- [ ] **Step 4: Extend `AnalogInWidget.__init__`**

Find (lines ~33-43):

```python
class AnalogInWidget(Widget):
    def __init__(self, signal: AnalogIn, theme: Theme | None = None) -> None:
        super().__init__()
        self.signal = signal
        self.theme_def = theme
        self.displayed_value: float = signal.min
        self._raw: float | None = None
        self.state_class: str = "state-ok"
        # ``False`` until the first reading arrives; drives the diffuse (dimmed)
        # render so a signal that has never reported reads as "no signal".
        self.has_data: bool = False
```

Replace with:

```python
class AnalogInWidget(Widget):
    can_focus = True

    def __init__(self, signal: AnalogIn, theme: Theme | None = None) -> None:
        super().__init__()
        self.signal = signal
        self.theme_def = theme
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
```

- [ ] **Step 5: Thread `ts` into `update_value` and capture history**

Find (lines ~45-65):

```python
    def update_value(self, value: float) -> None:
        """Apply ``value`` to the widget and schedule a redraw.

        Thread-safety: must be called from the Textual event-loop thread.
        Mutates ``displayed_value`` and ``state_class`` without a lock and then
        calls ``refresh()`` which queues a render message; both are unsafe from
        other threads. From a worker thread (e.g. the frame loop) hop via
        ``App.call_from_thread(widget.update_value, value)``.
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
        self.refresh()
```

Replace with:

```python
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
```

- [ ] **Step 6: Add sparkline helpers + click handler (after `_marker_at`, before `render_text`, lines ~83-85)**

Find:

```python
    def _marker_at(self) -> int:
        span = max(self.signal.max - self.signal.min, 1e-6)
        pct = (self.displayed_value - self.signal.min) / span
        pct = max(0.0, min(1.0, pct))
        return int(pct * (_BAR_WIDTH - 1))
```

Insert immediately after it:

```python
    def sparkline_str(self, width: int) -> str:
        """The analog sparkline glyph string for ``width`` columns, rendered
        against the current clock (``_now``)."""
        return render_analog(self._history.columns(self._now, width))

    def toggle_sparkline(self) -> None:
        self.expanded = not self.expanded
        self.refresh(layout=True)  # height changes 1 <-> 2 lines

    def tick(self, now: float) -> None:
        """Advance the render clock so a stopped signal scrolls into gaps."""
        self._now = max(self._now, now)

    def on_click(self) -> None:
        self.focus()
        self.toggle_sparkline()
```

- [ ] **Step 7: Render the second line when expanded**

Find the end of `render` (lines ~136-140):

```python
        val = f"{self.displayed_value:.{s.decimals}f}"
        text.append(f" {val}", style=value_style)
        if s.unit:
            text.append(f" {s.unit}", style=unit_style)
        return text
```

Replace with:

```python
        val = f"{self.displayed_value:.{s.decimals}f}"
        text.append(f" {val}", style=value_style)
        if s.unit:
            text.append(f" {s.unit}", style=unit_style)
        if self.expanded:
            width = max((self.content_size.width or 0) - 2, 0)
            spark = self.sparkline_str(width) if width >= 4 else ""
            if spark:
                text.append("\n  ")
                text.append(spark, style=c["bar_fill"])
        return text
```

- [ ] **Step 8: Clear history on instance switch**

Find (lines ~142-152):

```python
    def clear(self) -> None:
        """Reset to the no-data (diffuse) state.

        Used when the page switches NMEA instance so the previous instance's
        readings don't linger as if they were the new instance's data.
        """
        self.has_data = False
        self._raw = None
        self.displayed_value = self.signal.min
        self.state_class = "state-ok"
        self.refresh()
```

Replace with:

```python
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
        self.refresh()
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_widgets_sparkline.py tests/test_widgets_analog_in.py -v`
Expected: PASS (new sparkline tests + the existing analog-in tests still green).

- [ ] **Step 10: Commit & push**

```bash
git add src/pgntui/signals/widgets.py tests/test_widgets_sparkline.py
git commit -m "feat(widgets): AnalogInWidget captures history, expands, focusable"
git push origin main
```

---

## Task 4: `DigitalInWidget` — capture history, expand, focus

**Files:**
- Modify: `src/pgntui/signals/widgets.py` (`DigitalInWidget`, lines ~204-253)
- Test: append to `tests/test_widgets_sparkline.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_widgets_sparkline.py`)**

```python
from pgntui.signals.base import DigitalIn
from pgntui.signals.widgets import DigitalInWidget


def _dsig(**kw) -> DigitalIn:
    base = dict(id="run", type="digital_in", title="Bilge", pgn=127501,
                field="Indicator1", on_label="RUN", off_label="OFF")
    base.update(kw)
    return DigitalIn(**base)


def test_digital_update_value_with_ts_feeds_step_history() -> None:
    w = DigitalInWidget(_dsig())
    w.update_value(False, ts=0.0)
    w.update_value(True, ts=1.0)
    w.update_value(True, ts=2.0)
    assert w.sparkline_str(3) == "▁██"


def test_digital_clear_empties_history() -> None:
    w = DigitalInWidget(_dsig())
    w.update_value(True, ts=0.0)
    w.clear()
    assert w.sparkline_str(2) == "  "


def test_digital_is_focusable() -> None:
    assert DigitalInWidget(_dsig()).can_focus is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_widgets_sparkline.py -k digital -v`
Expected: FAIL — `AttributeError` / `can_focus` is False.

- [ ] **Step 3: Extend `DigitalInWidget.__init__`**

Find (lines ~204-211):

```python
class DigitalInWidget(Widget):
    def __init__(self, signal: DigitalIn, theme: Theme | None = None) -> None:
        super().__init__()
        self.signal = signal
        self.theme_def = theme
        self.value: bool = False
        # ``False`` until the first reading arrives — see AnalogInWidget.has_data.
        self.has_data: bool = False
```

Replace with:

```python
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
```

- [ ] **Step 4: Thread `ts` into `update_value` and capture 0/1 history**

Find (lines ~213-219):

```python
    def update_value(self, value: object) -> None:
        self.has_data = True
        if self.signal.bit is not None:
            self.value = bool((int(value) >> self.signal.bit) & 1)  # type: ignore[call-overload]
        else:
            self.value = bool(value)
        self.refresh()
```

Replace with:

```python
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
```

- [ ] **Step 5: Add helpers + click handler (after `update_value`, before `render_text`, line ~221)**

Insert before `def render_text` (~line 221):

```python
    def sparkline_str(self, width: int) -> str:
        """The digital step-wave glyph string for ``width`` columns."""
        return render_digital(self._history.columns(self._now, width))

    def toggle_sparkline(self) -> None:
        self.expanded = not self.expanded
        self.refresh(layout=True)

    def tick(self, now: float) -> None:
        self._now = max(self._now, now)

    def on_click(self) -> None:
        self.focus()
        self.toggle_sparkline()

```

- [ ] **Step 6: Render the second line when expanded**

Find the end of `DigitalInWidget.render` (lines ~241-247):

```python
        if self.value:
            text.append(_glyph(theme, "on"), style=c["ok"])
            text.append(f" {s.on_label}", style=c["fg"])
        else:
            text.append(_glyph(theme, "off"), style=c["fg_dim"])
            text.append(f" {s.off_label}", style=c["fg_dim"])
        return text
```

Replace with:

```python
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
                text.append("\n  ")
                text.append(spark, style=c["bar_fill"])
        return text
```

- [ ] **Step 7: Clear history in `clear()`**

Find (lines ~249-253):

```python
    def clear(self) -> None:
        """Reset to the no-data (diffuse) state on instance switch."""
        self.has_data = False
        self.value = False
        self.refresh()
```

Replace with:

```python
    def clear(self) -> None:
        """Reset to the no-data (diffuse) state on instance switch."""
        self.has_data = False
        self.value = False
        self._history.clear()
        self.refresh()
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_widgets_sparkline.py tests/test_widgets_digital_in.py -v`
Expected: PASS (digital sparkline tests + existing digital-in tests still green).

- [ ] **Step 9: Commit & push**

```bash
git add src/pgntui/signals/widgets.py tests/test_widgets_sparkline.py
git commit -m "feat(widgets): DigitalInWidget step-wave history, expands, focusable"
git push origin main
```

---

## Task 5: `PageView` CSS — allow row growth + focus highlight

**Files:**
- Modify: `src/pgntui/pages/view.py` (`DEFAULT_CSS`, lines ~97-127)
- Test: append to `tests/test_page_view.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_page_view.py`)**

```python
@pytest.mark.asyncio
async def test_expanded_widget_grows_to_two_lines() -> None:
    async with _Host().run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        w = pilot.app.query_one(AnalogInWidget)
        assert w.region.height == 1  # collapsed stays tight
        # feed a couple of timestamped readings, then expand
        w.update_value(1000.0, ts=0.0)
        w.update_value(5000.0, ts=1.0)
        w.toggle_sparkline()
        await pilot.pause()
        assert w.region.height == 2  # row grew to show the sparkline
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_page_view.py::test_expanded_widget_grows_to_two_lines -v`
Expected: FAIL — `region.height` stays 1 (grid row is pinned to height 1).

- [ ] **Step 3: Update the CSS**

Find (lines ~104-115):

```python
    PageView Grid {
        grid-rows: 1;
        grid-gutter: 0;
        height: auto;
    }
    PageView AnalogInWidget,
    PageView AnalogOutWidget,
    PageView DigitalInWidget,
    PageView DigitalOutWidget,
    PageView GroupRule {
        height: 1;
    }
```

Replace with:

```python
    PageView Grid {
        grid-rows: auto;
        grid-gutter: 0;
        height: auto;
    }
    /* Inputs can expand to a second line (sparkline), so they size to content;
       a collapsed widget still measures one line, keeping rows tight. */
    PageView AnalogInWidget,
    PageView DigitalInWidget {
        height: auto;
    }
    PageView AnalogOutWidget,
    PageView DigitalOutWidget,
    PageView GroupRule {
        height: 1;
    }
    PageView AnalogInWidget:focus,
    PageView DigitalInWidget:focus {
        background: $boost;
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_page_view.py -v`
Expected: PASS (new growth test + existing PageView tests still green).

- [ ] **Step 5: Commit & push**

```bash
git add src/pgntui/pages/view.py tests/test_page_view.py
git commit -m "feat(pageview): rows grow for sparkline + focus highlight"
git push origin main
```

---

## Task 6: `app.py` — clock + forward timestamp into the data path

**Files:**
- Modify: `src/pgntui/app.py` (`__init__` ~500-532; `_handle_frame` ~613-647; `_apply_update` ~649-656)
- Test: `tests/test_app_sparkline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app_sparkline.py
from __future__ import annotations

import asyncio

import pytest

from pgntui.app import PgntuiApp
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalKey, SignalRouter
from pgntui.drivers.base import Frame
from pgntui.pages.loader import Container, Page, SignalPlacement
from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget
from pgntui.themes.loader import load_builtin


def _rpm() -> AnalogIn:
    return AnalogIn(id="rpm", type="analog_in", title="RPM", pgn=127488,
                    field="Engine Speed", min=0, max=6000, smoothing=0.0)


def _page() -> Page:
    return Page(id="eng", title="Engine",
                containers=(Container(title="Drive", cols=12,
                            signals=(SignalPlacement("rpm", 0, 0, 12),)),))


def _app() -> PgntuiApp:
    router = SignalRouter()
    router.bind("rpm", SignalKey(pgn=127488, field="Engine Speed"))
    return PgntuiApp(theme=load_builtin("dark"), signals={"rpm": _rpm()},
                     pages=[_page()], decoder=CanboatDecoder.load_bundled(),
                     router=router, debug_buffer=DebugBuffer())


def _frame(rpm: float, ts: float) -> Frame:
    raw = round(rpm / 0.25)  # 127488 Engine Speed resolution
    data = bytes([0xFF, raw & 0xFF, (raw >> 8) & 0xFF, 0xFF, 0xFF, 0x7F])
    return Frame(timestamp=ts, source_addr=0, pgn=127488, data=data)


@pytest.mark.asyncio
async def test_frame_timestamp_populates_history_and_clock() -> None:
    app = _app()
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        w = app.query_one(AnalogInWidget)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, app._handle_frame, _frame(1000.0, 10.0))
        await loop.run_in_executor(None, app._handle_frame, _frame(5000.0, 11.0))
        await pilot.pause()
        assert app._clock == 11.0
        assert w.sparkline_str(2) == "▁█"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_app_sparkline.py -v`
Expected: FAIL — `AttributeError: 'PgntuiApp' object has no attribute '_clock'`.

- [ ] **Step 3: Add `_clock` to `__init__`**

Find (lines ~513-514):

```python
        self._debug_buffer = debug_buffer or DebugBuffer()
        self._page_titles = page_titles
```

Replace with:

```python
        self._debug_buffer = debug_buffer or DebugBuffer()
        self._page_titles = page_titles
        # Shared sparkline clock — the latest frame timestamp seen. Expanded
        # sparklines render their window ending at this value.
        self._clock: float = 0.0
```

- [ ] **Step 4: Update `_clock` and forward the timestamp in `_handle_frame`**

Find (lines ~627-647):

```python
        decoded = self._decoder.decode(frame)
        if decoded is None:
            return
        self._debug_buffer.push(decoded)
```

Replace with:

```python
        decoded = self._decoder.decode(frame)
        if decoded is None:
            return
        self._clock = max(self._clock, decoded.timestamp)
        self._debug_buffer.push(decoded)
```

Then find (lines ~640-647):

```python
                if (
                    view is not None
                    and view.page.instances
                    and view.active_instance_id != update.instance
                ):
                    continue
                self.call_from_thread(self._apply_update, w, update.value)
```

Replace with:

```python
                if (
                    view is not None
                    and view.page.instances
                    and view.active_instance_id != update.instance
                ):
                    continue
                self.call_from_thread(self._apply_update, w, update.value, update.timestamp)
```

- [ ] **Step 5: Thread `ts` through `_apply_update`**

Find (lines ~649-656):

```python
    @staticmethod
    def _apply_update(widget: Widget, value: object) -> None:
        if isinstance(widget, AnalogInWidget):
            widget.update_value(float(value))  # type: ignore[arg-type]
        elif isinstance(widget, DigitalInWidget):
            # Hand over the raw decoded value — the widget may need the full
            # integer bitfield to extract its configured ``bit``.
            widget.update_value(value)
```

Replace with:

```python
    @staticmethod
    def _apply_update(widget: Widget, value: object, ts: float | None = None) -> None:
        if isinstance(widget, AnalogInWidget):
            widget.update_value(float(value), ts)  # type: ignore[arg-type]
        elif isinstance(widget, DigitalInWidget):
            # Hand over the raw decoded value — the widget may need the full
            # integer bitfield to extract its configured ``bit``.
            widget.update_value(value, ts)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_app_sparkline.py tests/test_instance_switch.py tests/test_app_frame_loop.py -v`
Expected: PASS (new clock/history test + existing frame-path tests still green).

- [ ] **Step 7: Commit & push**

```bash
git add src/pgntui/app.py tests/test_app_sparkline.py
git commit -m "feat(app): shared sparkline clock + forward frame timestamp to widgets"
git push origin main
```

---

## Task 7: `app.py` — bindings, actions, repaint timer

**Files:**
- Modify: `src/pgntui/app.py` (`BINDINGS` ~467-480; `on_mount` ~536-551; actions near ~726-761)
- Test: append to `tests/test_app_sparkline.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_app_sparkline.py`)**

```python
@pytest.mark.asyncio
async def test_plus_toggles_focused_sparkline() -> None:
    app = _app()
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        w = app.query_one(AnalogInWidget)
        w.focus()
        await pilot.pause()
        await pilot.press("+")
        await pilot.pause()
        assert w.expanded is True
        await pilot.press("+")
        await pilot.pause()
        assert w.expanded is False


@pytest.mark.asyncio
async def test_down_moves_focus_to_a_signal_row() -> None:
    app = _app()
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert isinstance(app.focused, AnalogInWidget)


@pytest.mark.asyncio
async def test_repaint_tick_advances_expanded_widget_clock() -> None:
    app = _app()
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        w = app.query_one(AnalogInWidget)
        w.update_value(3000.0, ts=0.0)
        w.toggle_sparkline()
        app._clock = 5.0  # 5 s elapsed (would come from later frames)
        app._tick_sparklines()
        await pilot.pause()
        assert w._now == 5.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_app_sparkline.py -k "plus or down or repaint" -v`
Expected: FAIL — bindings/actions/`_tick_sparklines` not defined.

- [ ] **Step 3: Add the bindings**

Find (lines ~467-480):

```python
    BINDINGS = [
        ("tab", "next_container", "Next"),
        ("shift+tab", "prev_container", "Prev"),
        ("d", "show_debug", "Debug"),
        ("g", "toggle_debug_view", "Group"),
        ("r", "toggle_record", "Record"),
        ("left_square_bracket", "prev_instance", "Inst-"),
        ("right_square_bracket", "next_instance", "Inst+"),
        ("c", "connection", "Connection"),
        ("s", "config", "Config"),
        ("a", "about", "About"),
        ("q,ctrl+q", "force_quit", "Quit"),
        ("question_mark", "help", "Help"),
    ]
```

Replace with:

```python
    BINDINGS = [
        ("tab", "next_container", "Next"),
        ("shift+tab", "prev_container", "Prev"),
        ("up", "focus_prev_signal", "Up"),
        ("down", "focus_next_signal", "Down"),
        ("plus", "toggle_sparkline", "Spark"),
        ("d", "show_debug", "Debug"),
        ("g", "toggle_debug_view", "Group"),
        ("r", "toggle_record", "Record"),
        ("left_square_bracket", "prev_instance", "Inst-"),
        ("right_square_bracket", "next_instance", "Inst+"),
        ("c", "connection", "Connection"),
        ("s", "config", "Config"),
        ("a", "about", "About"),
        ("q,ctrl+q", "force_quit", "Quit"),
        ("question_mark", "help", "Help"),
    ]
```

- [ ] **Step 4: Start the repaint timer in `on_mount`**

Find (lines ~549-551):

```python
        self._wire_write_callbacks()
        if self._n2k_driver is not None and self._decoder is not None and self._router is not None:
            self.frame_loop()
```

Replace with:

```python
        self._wire_write_callbacks()
        # Repaint expanded sparklines once a second so a stopped signal scrolls
        # left into trailing gaps even when no new frames arrive for it.
        self.set_interval(1.0, self._tick_sparklines)
        if self._n2k_driver is not None and self._decoder is not None and self._router is not None:
            self.frame_loop()
```

- [ ] **Step 5: Add the actions + tick + focus mover (after `action_prev_container`, ~line 733)**

Insert after `action_prev_container` (the method ending at ~line 732):

```python
    def action_toggle_sparkline(self) -> None:
        w = self.focused
        if isinstance(w, (AnalogInWidget, DigitalInWidget)):
            w.toggle_sparkline()

    def action_focus_next_signal(self) -> None:
        self._move_signal_focus(1)

    def action_focus_prev_signal(self) -> None:
        self._move_signal_focus(-1)

    def _move_signal_focus(self, delta: int) -> None:
        view = self._active_view()
        if view is None:
            return
        widgets = [
            w
            for w in view.widgets.values()
            if isinstance(w, (AnalogInWidget, DigitalInWidget))
        ]
        if not widgets:
            return
        cur = self.focused
        if cur in widgets:
            idx = (widgets.index(cur) + delta) % len(widgets)
        else:
            idx = 0 if delta > 0 else len(widgets) - 1
        widgets[idx].focus()

    def _tick_sparklines(self) -> None:
        for widgets in self._widgets_by_signal.values():
            for w in widgets:
                if isinstance(w, (AnalogInWidget, DigitalInWidget)) and w.expanded:
                    w.tick(self._clock)
                    w.refresh()
```

Note: `_active_view` already exists (lines ~753-761); `_widgets_by_signal` is populated in `_wire_write_callbacks`. `AnalogInWidget`/`DigitalInWidget` are already imported in `app.py`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_app_sparkline.py -v`
Expected: PASS (all sparkline app tests).

- [ ] **Step 7: Commit & push**

```bash
git add src/pgntui/app.py tests/test_app_sparkline.py
git commit -m "feat(app): + toggles spark, up/down move row focus, 1s repaint timer"
git push origin main
```

---

## Task 8: Version bump 0.4.0 + release note

**Files:**
- Modify: `src/pgntui/__init__.py:3`, `pyproject.toml:7`, `src/pgntui/about.py:18-19`

- [ ] **Step 1: Bump `__version__`**

In `src/pgntui/__init__.py` find `__version__ = "0.3.13"` and replace with `__version__ = "0.4.0"`.

- [ ] **Step 2: Bump `pyproject.toml`**

Find `version = "0.3.13"` and replace with `version = "0.4.0"`.

- [ ] **Step 3: Add the release note (newest first)**

In `src/pgntui/about.py` find:

```python
RELEASE_NOTES: tuple[tuple[str, str], ...] = (
    ("0.3.13", "Signals stay dimmed until they report (no-data look)."),
```

Replace with:

```python
RELEASE_NOTES: tuple[tuple[str, str], ...] = (
    ("0.4.0", "Sparklines: press + (or click) a signal for its history."),
    ("0.3.13", "Signals stay dimmed until they report (no-data look)."),
```

- [ ] **Step 4: Run the consistency test**

Run: `.venv\Scripts\python.exe -m pytest tests/test_basics.py tests/test_about.py -v`
Expected: PASS (`about.RELEASE_NOTES[0][0] == __version__` now `"0.4.0"`).

- [ ] **Step 5: Commit & push**

```bash
git add src/pgntui/__init__.py pyproject.toml src/pgntui/about.py
git commit -m "chore(release): 0.4.0 - per-signal sparklines"
git push origin main
```

---

## Task 9: Full verification + headless visual check

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS — all prior tests plus the ~19 new ones (history 6, sparkline 7, widgets 9, page_view 1, app 4... count may vary). No failures.

- [ ] **Step 2: Lint + format + types**

Run:
```bash
.venv\Scripts\python.exe -m ruff check src tests
.venv\Scripts\python.exe -m ruff format src tests
.venv\Scripts\python.exe -m mypy src
```
Expected: ruff clean, format makes no changes (or commit them), mypy clean.

- [ ] **Step 3: Headless visual check (the prior-session lesson — verify what the user sees, don't assume)**

Save as `scripts/_spark_shot.py` (delete after), then run `.venv\Scripts\python.exe scripts/_spark_shot.py` and open `spark.svg`:

```python
import asyncio
from pgntui.app import PgntuiApp
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalKey, SignalRouter
from pgntui.drivers.base import Frame
from pgntui.pages.loader import Container, Page, SignalPlacement
from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget
from pgntui.themes.loader import load_builtin


async def main() -> None:
    router = SignalRouter()
    router.bind("rpm", SignalKey(pgn=127488, field="Engine Speed"))
    app = PgntuiApp(
        theme=load_builtin("dark"),
        signals={"rpm": AnalogIn(id="rpm", type="analog_in", title="Engine Speed",
                                 pgn=127488, field="Engine Speed", unit="rpm",
                                 min=0, max=6000, smoothing=0.0)},
        pages=[Page(id="eng", title="Engine",
                    containers=(Container(title="Drive", cols=12,
                                signals=(SignalPlacement("rpm", 0, 0, 12),)),))],
        decoder=CanboatDecoder.load_bundled(), router=router, debug_buffer=DebugBuffer(),
    )
    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause()
        w = app.query_one(AnalogInWidget)
        for i in range(40):
            w.update_value(2000 + 1500 * (i % 8), ts=float(i))
        app._clock = 39.0
        w.toggle_sparkline()
        await pilot.pause()
        app.save_screenshot("spark.svg")


asyncio.run(main())
```
Expected: `spark.svg` shows the "Engine Speed" row with a block-eighth sparkline on a second line beneath it. Confirm visually, then delete `scripts/_spark_shot.py` and `spark.svg`.

- [ ] **Step 4: Final commit (only if ruff format changed files)**

```bash
git add -A
git commit -m "style: ruff format after sparklines"
git push origin main
```

---

## Self-review notes (author check — done)

- **Spec coverage:** per-signal reveal (Task 7 `+`/click via `on_click`), keyboard cursor (Task 7 up/down), time-bucketed history (Task 1), gaps + scroll-into-gaps (Tasks 1, 3, 7), auto-scale (Task 2), analog block-eighths + digital step wave (Tasks 2-4), inputs-only (outputs untouched), instance-switch clears history (Tasks 3-4), repaint timer/shared clock (Tasks 6-7), version bump (Task 8), headless verify (Task 9). All covered.
- **Type/name consistency:** `History(bucket_seconds, capacity)`, `.add(value, ts)`, `.columns(now, width)`, `.clear()`, `len()`; `render_analog/render_digital(cols)`; widget `sparkline_str(width)`, `toggle_sparkline()`, `tick(now)`, `expanded`, `_now`, `_history`; app `_clock`, `_tick_sparklines`, `_apply_update(widget, value, ts)`, `action_toggle_sparkline`, `action_focus_next_signal`/`action_focus_prev_signal`, `_move_signal_focus`. Consistent across tasks.
- **Backward compatibility:** `update_value(value, ts=None)` keeps legacy callers (existing widget tests) working; `_apply_update` ts defaulted; collapsed widgets still measure 1 line (existing `test_page_view` assertion preserved).
- **Risk to watch during execution:** `up`/`down` must beat any PageView scroll handling (app BINDINGS fire when the focused signal widget doesn't consume the key — verified by the focus test); if a conflict appears, mark those two `Binding(..., show=False)` and/or use a non-arrow key.
