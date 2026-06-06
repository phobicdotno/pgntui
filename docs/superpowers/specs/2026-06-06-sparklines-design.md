# Sparklines — design

- **Date:** 2026-06-06
- **Status:** Approved (design); pending implementation plan
- **Feature:** Per-signal historical sparklines, revealed on demand under a signal row.

## Goal

Let the user reveal a compact historical sparkline beneath any input signal row,
so trends and dropouts are visible in context without leaving the page. Analog
signals render as a block-eighth amplitude trace; digital signals render as a
step (square) wave. History is time-bucketed, so the horizontal axis is real
wall-clock time and silent periods show as gaps.

## Locked requirements

| Decision | Choice |
|---|---|
| Reveal | **Per-signal.** Keyboard cursor + a key on the focused row, **and** mouse-click toggle. |
| Time axis | **Time-bucketed by timestamp.** Each column is a fixed wall-clock bucket; silent buckets render as gaps. |
| Vertical scale | **Auto-scale to the visible window** (analog): lowest..highest value in view maps to full height. |
| Scope (v1) | **Analog and digital inputs.** Analog = block eighths; digital = step wave. |

## Non-goals (v1)

- No sparkline on **outputs** (`AnalogOut` / `DigitalOut`) — they have no inbound history.
- No page-wide "expand everything" toggle — reveal is per-signal.
- No configurable bucket width / window length yet (fixed defaults; configurable later).
- No per-bucket min/max or average — each bucket keeps the **last** value seen (see Open choices).
- No persistence of history across runs or across instance switches.

## Approaches considered

1. **Row expansion (1→2 lines).** *Chosen:* the signal widget renders its own
   optional second line (`height: auto`, grid `grid-rows: auto`). *Rejected:* a
   separate child widget mounted into the grid (auto-flow places it at the end,
   not under the toggled row — needs grid rebuilds); a single bottom "inspector"
   pane (loses inline context, only one signal at a time).
2. **History storage.** *Chosen:* a `History` helper owned by each widget
   (composition) — `clear()` on instance-switch stays trivial and render is
   local, while `History` remains an isolated, unit-testable unit. *Rejected:* an
   app-owned buffer index keyed by signal ref (extra lifetime/clear coordination).
3. **Selection model.** *Chosen:* native Textual focus (`can_focus = True`,
   `:focus` highlight, ↑/↓ to move the row cursor) — gives the highlight,
   keyboard, and click-to-focus for free. *Rejected:* a PageView-managed cursor
   index (reimplements focus highlighting).

## Architecture

### New units

#### `signals/history.py` — `History`

Time-bucketed sample store. Pure data; no glyphs, no theming.

```python
class History:
    def __init__(self, bucket_seconds: float = 1.0, capacity: int = 300) -> None: ...
    def add(self, value: float, ts: float) -> None: ...
    def columns(self, now: float, width: int) -> list[float | None]: ...
    def clear(self) -> None: ...
    def __len__(self) -> int: ...
```

- Bucket index = `int(ts // bucket_seconds)`.
- `add` keeps the **last** value written to a bucket; advancing to a newer bucket
  leaves intervening buckets simply absent (no fill).
- Evict the oldest bucket once stored buckets exceed `capacity` (~300 buckets =
  5 min at 1 s).
- `columns(now, width)` returns exactly `width` entries ending at
  `now_bucket = int(now // bucket_seconds)`: for `i in range(width)`, bucket =
  `now_bucket - (width - 1) + i`; the stored value or `None` if that bucket is
  empty (a gap). The right-most column is always "now", so a stopped signal
  scrolls left into trailing `None`s.

Digital signals reuse `History` with values `0.0` / `1.0`.

#### `signals/sparkline.py` — pure render functions

```python
def render_analog(cols: list[float | None]) -> str: ...
def render_digital(cols: list[float | None]) -> str: ...
```

- Glyph ramp (analog): `"▁▂▃▄▅▆▇█"` (8 levels). Gap (`None`) → space `" "`.
- `render_analog`: from the non-`None` values take `vmin`, `vmax`.
  - No data at all → all spaces.
  - `vmax == vmin` (flat or single point) → mid glyph `▄` for data columns,
    space for gaps (avoids divide-by-zero and noise amplification on a steady
    signal).
  - Otherwise `level = round((v - vmin) / (vmax - vmin) * 7)` → `ramp[level]`.
- `render_digital`: value ≥ 0.5 → `█` (on), value < 0.5 → `▁` (off), `None` → space.

Both return a plain glyph string; the widget wraps it in a themed `Text` and
applies color. Unit-tested directly with hand-built `cols` lists.

### Changed units

#### `signals/widgets.py` — `AnalogInWidget`, `DigitalInWidget`

- Compose a `History` instance.
- `update_value(value, ts)` — gains the `ts` parameter; after computing the
  displayed value (analog) or boolean (digital), append to history:
  - analog: `history.add(self.displayed_value, ts)` (display units — the spark is
    the bar's history), and `self._now = max(self._now, ts)`.
  - digital: `history.add(1.0 if self.value else 0.0, ts)`, same `_now` update.
- `expanded: bool` flag + `toggle_sparkline()` / `set_expanded(bool)`.
- `tick(now: float)` — set `self._now = max(self._now, now)` (called by the app
  repaint timer so the window advances even without new readings).
- `can_focus = True`; `on_click` → focus self and toggle expansion.
- `render()` — returns the existing single line normally; when `expanded`,
  returns two lines joined by `\n`: the row, then a sparkline line indented 2
  columns, spanning the available content width, in accent color (gaps are
  spaces). Width = `max(content width - 2, 0)`; if too small (< ~4) render the row
  only.
- `clear()` — also calls `history.clear()` (instance switch = new data series);
  keeps `expanded` as-is so the row stays open and fills with gaps until new data.

#### `pages/view.py` — `PageView`

- CSS: `PageView Grid { grid-rows: 1 }` → `grid-rows: auto`; signal widgets
  `height: 1` → `height: auto` (a collapsed widget still measures 1 line, so tight
  rows are preserved; an expanded widget measures 2).
- Add a `:focus` highlight for the input widgets (subtle background via the theme,
  e.g. `$boost`).

#### `app.py`

- `_apply_update(widget, value)` → `_apply_update(widget, value, ts)`; forward
  `update.timestamp` (already present on `SignalUpdate`) and call
  `widget.update_value(value, ts)`.
- Shared clock: `self._clock: float`, updated to `max(self._clock,
  decoded.timestamp)` in `_handle_frame`.
- Repaint timer: `set_interval(1.0, self._tick_sparklines)` in `on_mount`. The
  callback walks expanded input widgets, calls `w.tick(self._clock)` and
  `w.refresh()` so a stopped signal scrolls into trailing gaps. No-op (cheap) when
  nothing is expanded; may be paused/resumed on toggle as an optimization.
- Bindings: `+` → `action_toggle_sparkline` (acts on `self.focused` if it is an
  input widget); `up` / `down` → move the row cursor among the active page's
  focusable input widgets (wrapping). Footer label for `+`: "Spark".
- `Tab` / `Shift+Tab` (page nav) and `[` / `]` (instance) are unchanged.

## Data flow

```
frame ─▶ decode ─▶ SignalRouter.route ─▶ SignalUpdate{value, timestamp, instance}
        │                                         │
        └── decoded.timestamp ─▶ app._clock        ▼
                                   _apply_update(widget, value, ts)
                                        ▼
                                   widget.update_value(value, ts)
                                        ▼
                                   History.add(value, ts)

render: History.columns(widget._now, width) ─▶ render_analog/render_digital ─▶ themed 2nd line
repaint timer (1 s): widget.tick(app._clock) + widget.refresh()
```

## Interaction model

- **↑ / ↓** — move the highlighted row cursor among the current page's input
  signals (wraps top/bottom).
- **`+`** — toggle the sparkline on the focused row (footer: "Spark").
- **Click** — click any input row to focus it and toggle its sparkline.
- **`[` / `]`** — instance switch clears history for that page's widgets (new
  series); expanded rows stay open and refill from gaps.
- Multiple rows can be expanded at once.

## Edge cases

- **Flat / single-sample window** (`vmax == vmin`) → flat mid line `▄`; no
  divide-by-zero.
- **No data yet** → an expanded row shows an all-gap (blank) sparkline line,
  consistent with the diffuse no-data look.
- **Stopped signal** → right edge tracks `app._clock`, so it scrolls into trailing
  gaps. If the **entire** bus goes silent, the clock freezes (acceptable).
- **Replay vs live** → both carry per-frame timestamps, so bucketing and the
  shared clock work identically.
- **Multi-column container** → expanding one cell grows its whole grid row (blank
  appears under the row-neighbor). Most containers are single-column; acceptable
  for v1.
- **Digital bitfields** → history stores the extracted bit (`0`/`1`), matching
  `widget.value`.

## Testing

- **`history.py`** — bucket assignment by `ts`; last-value-per-bucket; gaps for
  skipped buckets; eviction at `capacity`; `columns(now, width)` window mapping and
  right-edge = now; `clear()`.
- **`sparkline.py`** — analog level mapping (0..7), auto-scale, flat-window mid
  line, all-gap, leading/trailing gaps; digital on/off/gap; assorted widths.
- **Widgets** — `update_value(value, ts)` feeds history; `toggle_sparkline()` →
  two-line render; `tick()` advances the window; `clear()` empties history; click
  toggles; focus highlight present.
- **Pilot (`App.run_test`)** — ↑/↓ move focus; `+` toggles the focused row; the
  repaint tick refreshes an expanded row; instance switch clears history.
- **Headless visual check** — `App.run_test(size=...)` + `export_screenshot()` to
  eyeball the real rendering before claiming done (per the prior session's lesson:
  verify what the user actually sees, don't assume).

## Versioning / release

- Bump **0.3.13 → 0.4.0** (feature) across the three spots — `pyproject.toml`,
  `src/pgntui/__init__.py` (`__version__`), and the top of `about.RELEASE_NOTES`
  (consistency enforced by `tests/test_basics.py`).
- Add a `RELEASE_NOTES` line describing per-signal sparklines.

## Open choices (defaulted; revisit only if needed)

- **Per-bucket value:** last value seen (vs. average or min/max). Last is simplest
  and faithful to "most recent in that second"; min/max could be a later option to
  surface spikes.
- **Bucket width / window:** fixed `bucket_seconds = 1.0`, `capacity = 300`;
  window width = available row width. Make configurable later if requested.
- **Sparkline placement:** indented 2 columns, spanning full content width (max
  history resolution), accent color, gaps as spaces.
