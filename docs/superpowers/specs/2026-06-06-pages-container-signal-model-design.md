# Page → Container → Signal model (design)

**Date:** 2026-06-06
**Status:** Approved (pending spec review)
**Decision:** Approach (c) — adopt a nested schema, **new format only** (no back-compat reader); ship a one-time migrator for existing workspaces.

## Problem

The dashboard renders as tabs, one per workspace file ("container"). Each file
declares `groups` (rendered as titled boxes since the group-box change) and a
flat list of `signals` positioned by absolute `row`/`col`. Two failure modes
fall out of this flat shape:

1. **Naked signals.** A signal whose `row` sits above the first group header
   belongs to no box. On the Engine page, `Engine RPM` renders full-width and
   loose, above the first box — visually orphaned.
2. **Box-less pages.** A file with no `groups` (Main) renders one ungrouped
   grid — a bare, uneven scatter of signals with no structure, inconsistent
   with the boxed pages.

Rendered evidence (current `main`):

```
NavEngineMainDebug
Engine RPM   Speed (SOW)   Depth   Water Temp     <- jammed, no boxes
Target Heading        0.00 rad [disabled]
Bilge Alarm  ○ DRY    Anchor Light [○ OFF]
```

Root cause: the model has no enforced "box" level. "Group" is an optional,
row-positioned decoration rather than a real container that *owns* its signals.

## Goal

Make the three-level hierarchy explicit and enforced:

```
Page  ──contains──>  Container(s)  ──contains──>  Signal(s)
```

Every Signal lives in exactly one Container; every Container lives on a Page.
This eliminates naked signals and box-less pages by construction, and gives a
natural home for a runtime-**generated** "Auto" page (phase 2).

### Non-goals
- No change to the signal **decode/route** pipeline (`CanboatDecoder`,
  `SignalRouter`, `DecodedFrame`) — only how display is modelled and rendered.
- No back-compat for the old flat schema at runtime (a migrator converts it
  once instead).

## Terminology / rename

| Concept | Today (code) | After |
|---|---|---|
| **Page** — one tab | `Container` dataclass; `nav.json` | `Page` dataclass |
| **Container** — titled box that owns a grid of signals | `GroupHeader` + flat `signals` | `Container` dataclass |
| **Signal** — a reading widget | `Signal` / `SignalPlacement` | unchanged (placement is now container-relative) |

The existing `GroupBox` widget becomes the **Container** renderer. `GroupRule`
is retained only for the page-level instance header (`◀ Engine Stb (0) ▶`).

## Data model

`pgntui/containers/loader.py` — **keep the package path** `pgntui/containers/`
in phase 1 (rename symbols only, not files, to limit blast radius; a package
rename to `pages/` is an optional later cleanup). `ContainerLoadError` →
`PageLoadError`:

```python
@dataclass(frozen=True, slots=True)
class SignalPlacement:
    ref: str            # signal id
    row: int            # row WITHIN the container's grid (was page-absolute)
    col: int
    w: int

@dataclass(frozen=True, slots=True)
class Container:
    title: str
    cols: int                       # grid width, per-container (default 12)
    signals: tuple[SignalPlacement, ...]

@dataclass(frozen=True, slots=True)
class InstanceOption:
    id: int
    label: str

@dataclass(frozen=True, slots=True)
class Page:
    id: str
    title: str
    containers: tuple[Container, ...]
    instances: tuple[InstanceOption, ...] = ()   # page-level; [ / ] switch
    generated: bool = False                      # phase 2: Auto page
```

Validation (raise `PageLoadError`):
- `id`, `title` required; `containers` non-empty for authored pages.
- Every `signal.ref` resolves against the known signal ids.
- Within a container, placements must not overlap and must fit `cols`
  (`col + w <= cols`). Row/col are container-relative.
- A `generated: true` page must declare **no** containers (runtime fills it).

## JSON schema (new)

```jsonc
{
  "id": "engine",
  "title": "Engine",
  "instances": [
    { "id": 0, "label": "Engine Stb" },
    { "id": 1, "label": "Engine Port" }
  ],
  "containers": [
    {
      "title": "Drive",
      "cols": 12,
      "signals": [
        { "ref": "engine_rpm",     "row": 0, "col": 0, "w": 12 },
        { "ref": "boost_pressure", "row": 1, "col": 0, "w": 6  },
        { "ref": "tilt_trim",      "row": 1, "col": 6, "w": 6  }
      ]
    },
    {
      "title": "Oil & temperature",
      "cols": 12,
      "signals": [ /* ... */ ]
    }
  ]
}
```

Auto page (phase 2) ships as a tiny stub:

```jsonc
{ "id": "auto", "title": "Auto", "generated": true, "containers": [] }
```

## Rendering

`pgntui/containers/screen.py`:
- `PageView` (was `ContainerView`) renders one Page: an optional page-level
  instance header (`GroupRule`) at the top, then a `VerticalScroll` of its
  Containers.
- Each `Container` renders as a `GroupBox` (titled border) wrapping its own
  auto-flow `Grid` (the per-container grid we already build). Container height
  is `auto`; the page scrolls.
- `widgets` dict (ref → widget) is still exposed for routing; built across all
  containers on the page.

`pgntui/app.py`:
- `compose()` builds a `TabbedContent` with one `TabPane` per Page (id
  `tab-<page.id>`), plus the Auto page (phase 2) and the existing Debug tab.
- `_page_views: list[tuple[Page, PageView]]` replaces `_view_pairs`.
- Instance handling is **page-level**: `_active_view()` returns the PageView
  for the currently active tab; `[`/`]` switch that page's instance (only pages
  with `instances` respond). Existing per-frame instance filtering in the
  router/widgets is unchanged.

## Migration (no runtime back-compat)

The loader reads **only** the new schema. Existing workspaces (the bundled
examples and the user's `%LOCALAPPDATA%\pgntui\pgntui`) are converted once:

- `migrate_workspace(workspace) -> int` in `pgntui/__main__.py` (or a
  `pgntui/migrate.py`): for each `containers/*.json` in the old flat form
  (`groups` + page-absolute `signals`), produce the new nested form by bucketing
  signals under the nearest preceding group header (the same bucketing the
  group-box renderer does today), rebasing rows to be container-relative, and
  emitting `containers[]`. A file with no `groups` becomes a single Container
  titled by the page title (or `"Signals"`).
- CLI: `pgntui --migrate-workspace [--workspace PATH]` — backs up the old files
  to `containers.bak-flat/` and writes new ones. Idempotent (new-format files
  are passed through).
- The three bundled examples (`1-nav`, `2-engine`, `3-main`) are rewritten to
  the new schema in-repo as part of phase 1.

## Phase 2 — Auto generated page

A Page with `generated: true`, populated at runtime from the live stream +
canboat metadata (already available: `FieldType`, `Unit`, `Resolution`,
`RangeMin`, `RangeMax`, `LookupEnumeration`).

- Maintain a seen-set of `(pgn, source)`. On first sight, mount a Container
  titled by the PGN name (source in the title when >1 source); for each field,
  build a Signal: `NUMBER` → `AnalogIn` (min/max/unit from the DB, or auto-range
  from observed values when the DB range is unusable); `LOOKUP`/`BITLOOKUP` →
  a text/enum widget; `RESERVED`/spare skipped; anything else → raw text.
- Build **only on first-seen** (never per-frame). Mount via `call_from_thread`
  (frames arrive on the worker thread). Cap the number of containers; the page
  scrolls.

Phase 2 is designed here but planned/implemented separately from phase 1.

## Affected files

**Code:** `containers/loader.py` (rename + nested parse + validation +
migrator helpers), `containers/screen.py` (`ContainerView`→`PageView`,
Container=GroupBox), `app.py` (compose tabs per Page, `_page_views`, page-level
instance actions, Auto tab in phase 2), `__main__.py` (`discover_pages`,
`--migrate-workspace`, scaffold ships new format).

**Data:** `examples/containers/{1-nav,2-engine,3-main}.json` rewritten;
`examples/containers/4-auto.json` added (phase 2).

**Tests:** `test_container_groups.py`, `test_instance_switch.py`,
`test_app_container_visible.py`, `test_main_replay.py`,
`test_app_empty_welcome.py` updated for the new schema/ids; new
`test_pages_loader.py` (schema + validation), `test_migrate_workspace.py`
(old→new conversion), and phase 2 `test_auto_page.py`.

## Testing strategy

- Loader: new schema parses; validation rejects overlaps, overflow, unknown
  refs, empty authored pages, and containers on a generated page.
- Migrator: old flat file → expected nested file; no-`groups` file → single
  container; idempotent on new-format input; round-trips the 3 examples.
- Render: each example page mounts; every signal widget has non-zero region on
  its active tab (port of the current visibility regression test); each
  Container renders a `GroupBox` with the right `border_title`.
- Instances: page-level `[`/`]` switches Engine; non-instance pages ignore it.
- Phase 2: first-seen builds one container per PGN; repeats don't rebuild;
  field-type→widget mapping; cap respected.

## Phasing

- **Phase 1 (this plan):** rename + nested schema + `PageView` render + migrate
  examples + `--migrate-workspace`. Fixes Engine/Main immediately.
- **Phase 2 (next plan):** Auto generated page.

## Resolved decisions
- Schema: **new only**, no runtime back-compat (approach c). Migrator converts.
- Pages are always tabs (Nav | Engine | Main | Auto | Debug); tab strip stays.
- Instances are a **page-level** property.
- Auto page: **one container per `(pgn, source)`**, built on first-seen, capped.
