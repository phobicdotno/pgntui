# Auto page (Phase 2) — design

- **Date:** 2026-06-06
- **Status:** Approved (design); pending implementation plan
- **Feature:** An auto-populated "Auto" tab built at runtime from the live NMEA 2000 stream.

## Goal

Give the user a browsable, widget-rendered view of **everything** on the bus
without authoring a page first. Every `(pgn, source)` seen gets a titled
container; each decoded field becomes a row — numeric fields as a value row with
an on-demand sparkline, non-numeric fields as a text row. It is richer than the
Debug tab's flat table (real signal widgets + sparklines) and requires zero
configuration.

## Locked decisions

| Decision | Choice |
|---|---|
| Scope | **Everything seen** — every `(pgn, source)`, no mapped/unmapped filtering. |
| Granularity | **One Container per `(pgn, source)`**, titled `<pgn> <name> · src <n>`. |
| Numeric field | Value row + on-demand sparkline, **no bar** (auto signals have no curated min/max; the sparkline auto-scales). Reuse `AnalogInWidget` with a new `show_bar=False`. |
| Non-numeric field | Read-only **text row** (`AutoTextWidget`) — no sparkline. |
| Build timing | **First-seen at runtime**, mounted via `call_from_thread`; later frames update in place. |
| Bound | Cap at **50 containers** (configurable); once hit, stop adding new `(pgn, source)` (no eviction). |
| Order | First-seen (append); rows in field order. |

## Non-goals (v1)

- No lookup-label resolution — a field whose decoded value is an integer (incl.
  enums/lookups) renders as a numeric row showing that integer. Resolving enum
  labels is a later enhancement.
- No per-field units unless the value already carries them — units are
  best-effort (omitted if not trivially available). Later enhancement.
- No eviction / LRU at the cap — first 50 win; the rest are dropped with a note.
- No instance switcher — `source` already separates devices (one container each).
- No persistence — the Auto page is rebuilt each run.

## Architecture

### New units

#### `pages/auto.py` — `AutoPageBuilder`

Owns the runtime construction of the Auto page. Isolated and unit-testable
(takes a callback to mount widgets; no direct Textual app dependency beyond the
mount hook).

```python
class AutoPageBuilder:
    def __init__(self, view: PageView, *, write_enabled: bool,
                 theme: Theme | None, max_containers: int = 50) -> None: ...
    def ingest(self, decoded: DecodedFrame) -> None:
        """Called on the UI thread for each decoded frame. Creates a container
        for a new (pgn, source) (up to the cap), then updates that container's
        field rows with the frame's values."""
    @property
    def at_capacity(self) -> bool: ...
```

- Key = `(pgn, source_addr)`. Tracks `dict[key, dict[field_name, Widget]]`.
- On first sight of a key (and `len < max_containers`): build a `GroupBox(Grid)`
  with one row per field (numeric → `AnalogInWidget(show_bar=False)`, non-numeric
  → `AutoTextWidget`), mount it into the Auto `PageView`, register the rows.
- Numeric vs non-numeric decided at runtime: `isinstance(value, (int, float))`
  and not `bool`.
- On subsequent frames for a known key: push each field value to its row widget
  (`update_value(value, ts)` for numeric, `set_text(str(value))` for text).
- At capacity: ignore unseen keys; expose `at_capacity` so the app can show a
  status note once.

#### `signals/widgets.py` — `AutoTextWidget`

A minimal read-only row: `<title>   <value text>`. No bar, no sparkline, not
focusable. `set_text(text: str)` updates and refreshes.

### Changed units

- `signals/widgets.py` — `AnalogInWidget` gains `show_bar: bool = True`. When
  `False`, `render`/`render_text` omit the bar segment (keep title + value + unit
  + the `[+]` sparkline). All history/expand/focus logic is unchanged.
- `pages/loader.py` — already supports `generated: true`. Add a bundled
  `auto` page file (or construct the generated `Page` in code) titled "Auto".
- `app.py`:
  - In `compose`, add an **Auto** `TabPane` (a `PageView` over the generated Auto
    page) after the curated pages, before Debug — only when a driver is present.
  - Construct an `AutoPageBuilder` over that view in `on_mount`.
  - In `_handle_frame`, after the existing decode + debug + route, call
    `self.call_from_thread(self._auto_builder.ingest, decoded)`.
  - Show a one-time status note when the builder hits capacity.

## Data flow

```
frame ─▶ decode ─▶ DecodedFrame(pgn, source_addr, fields{name: value})
                        │
   (existing: debug buffer + router → curated widgets)
                        │
                        └─▶ call_from_thread(AutoPageBuilder.ingest, decoded)
                                  │ first sight of (pgn,src): build container+rows, mount
                                  └ known (pgn,src): update each field row
```

## Edge cases

- **Cap reached** → new `(pgn, source)` ignored; status note shown once
  (`"Auto: 50 sources (cap reached)"`).
- **Field set changes between frames** (rare) → unknown fields on a later frame
  are ignored; missing fields keep their last value. (No row add/remove after
  first build, for v1 simplicity.)
- **Non-numeric → numeric drift** → the row type is fixed at first build from the
  first value's type; a later type change keeps the original row (best-effort).
- **No driver** (placeholder/empty workspace) → no Auto tab (nothing to populate).
- **Thread-safety** → `ingest` only ever runs on the UI thread (via
  `call_from_thread`), so widget mounting/mutation is safe.

## Testing

- **`AutoPageBuilder`** (unit, with a stub/real `PageView` under `App.run_test`):
  first frame for a key creates one container with the right row types; a second
  frame updates values in place (no new container); a third distinct key adds a
  second container; the cap stops growth and flips `at_capacity`.
- **`AnalogInWidget(show_bar=False)`** — `render_text()` omits the bar but keeps
  title/value/unit and the `[+]`; the sparkline still works.
- **`AutoTextWidget`** — `set_text` updates the rendered text.
- **Pilot** — build an app with a replay/stub driver, feed frames, assert the
  Auto tab gains containers and shows values.
- **Headless screenshot** — render the Auto tab populated, eyeball it.

## Versioning / release

- Minor bump (feature): **0.4.3 → 0.5.0** across the three spots + an
  `about.RELEASE_NOTES` line; tag `v0.5.0` to release once green.

## Open choices (defaulted; revisit only if needed)

- **Cap = 50 containers**; configurable later via `config.toml`.
- **Container title** = `"<pgn> <name> · src <n>"`; falls back to `"<pgn> · src
  <n>"` when the decoder has no name.
- **Numeric detection** = runtime `isinstance(value, (int, float))` excluding
  `bool`; no reliance on canboat field-type metadata in v1.
