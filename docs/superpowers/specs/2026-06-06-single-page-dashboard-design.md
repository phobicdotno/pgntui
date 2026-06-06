# Single-Page Dashboard + Diffuse Signals — Design

**Goal:** Collapse the Nav / Engine / Main page tabs into one scrollable,
multi-column **dashboard** that shows every container at once, and dim signals
that have not reported ("diffuse" look) so silent inputs read as silent.

## Decisions

### Dashboard layout
- One `DashboardView` replaces the per-page `TabPane`s. The `TabbedContent`
  goes from `{Nav, Engine, Main, Debug}` → `{Dashboard, Debug}`; Debug is
  reached with `[D]`.
- Every container from every page JSON, concatenated in **page-file order**
  (nav → engine → main), is flowed into **K responsive columns**:
  `K = max(1, min(3, width // 46))`. Containers are distributed to balance
  estimated height (rows + borders) so columns stay even. The layout reflows on
  terminal resize.
- The `GroupBox` titled-border rendering is unchanged — boxes look exactly as
  they do today.

### Authoring (no migration)
- Each page JSON stays a file. "Pages" simply become *sections* rendered
  together on the one dashboard. The on-disk schema and the `Page`/`Container`
  loader are unchanged.

### Instances
- Default: keep the `[ / ]` instance selector (one instance shown at a time),
  rendered as a thin full-width header line above the columns. Inbound updates
  are routed to the active instance only (current behaviour, preserved).
- Future toggle (out of scope here): "show all instances" — expand each
  instanced container into one box per instance, with silent instances left
  diffuse. The diffuse work below makes this cheap to add later.

### Auto (generated) section — Phase 2, queued
- The previously-planned "Auto page" (`generated: true`) folds into the
  dashboard as an **Auto section**, not a separate tab: auto-discovered
  containers (one per `(pgn, source)`; NUMBER→AnalogIn, LOOKUP→text) append to
  the same column flow, mounted at runtime as each PGN is first seen on the
  wire. The dashboard's runtime-mount + responsive-column design is built to
  accept this; the generation logic itself stays out of scope for this change.

### Diffuse (no-data) signals
- Inbound widgets (`AnalogInWidget`, `DigitalInWidget`) gain `has_data`
  (`False` until the first reading). While `False`, the whole row renders in the
  theme's `fg_dim` — the same dimmed look already used for OFF/disabled items.
- On the first `update_value`, `has_data` flips `True` and the row renders
  live (state colours, bar fill).
- `clear()` returns a widget to the diffuse state; `PageView.set_active_instance`
  calls it on instance switch (instead of pushing a fake `min` reading, which
  previously made a freshly-switched, not-yet-reporting instance look live).
- A live OFF digital keeps a **bright title** so it stays distinct from a
  no-data digital (dim title). Outputs (`AnalogOut`/`DigitalOut`) are unchanged.

### Footer
- One page ⇒ one static hint strip. This supersedes the earlier "per-page
  footer" idea (a single page has a single footer).

## Out of scope / queued
- Sparklines (`[+]` history under a signal) — next feature after this.
- "Show all instances" toggle.
- Staleness timeout (dim a signal again after N seconds of silence).
