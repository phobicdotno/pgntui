# pgntui — Design Spec

**Date:** 2026-06-04
**Status:** Draft for review

## Summary

`pgntui` is a cross-platform terminal UI for NMEA 2000. It reads and (optionally) writes the bus through pluggable driver modules, decodes traffic via the canboat PGN database, and renders user-configurable dashboards composed of signal widgets laid out in grid containers. It supports live monitoring, raw PGN debugging, per-signal CSV logging, and full session record/replay.

Inspiration for the aesthetic is the dense, instrument-panel TUI style of the SquareWaveSystems opcilloscope dark theme: monospace, low chrome, hotkey strip at the bottom.

## Goals

- Run on macOS, Linux, and Windows (PowerShell)
- Pluggable driver modules — first-class drivers ship in v1; third-party drivers installable via `pip`
- Configurable dashboards driven by per-signal and per-container JSON files
- Read-only by default; write requires an explicit flag
- Decode 200+ standard PGNs via canboat
- Record live sessions and replay them through the same UI

## Non-Goals (v1)

- Chartplotter / map display
- SignalK server functionality (we may *consume* it via a driver later, but we don't host it)
- Mobile or web UI
- Multi-bus aggregation across multiple drivers simultaneously (one driver at a time in v1)
- Alarm push notifications (visual/audible only)

## Stack

- **Language:** Python 3.11+
- **TUI:** [Textual](https://textual.textualize.io/)
- **Serial:** `pyserial`
- **PGN database:** [canboat](https://github.com/canboat/canboat) `pgns.json`, bundled
- **Config:** TOML for app config, JSON for signals and containers
- **Packaging:** `uv` / `pipx` install; drivers as separate `pip` packages discovered via `entry_points`

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Textual App                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Tabs: [Engine Room] [Nav] [Helm] [Debug] [Rec]  │   │
│  │  ┌────────────────────────────────────────────┐  │   │
│  │  │           Active Container (grid)           │  │   │
│  │  │   ┌──────────────┐  ┌──────────────┐       │  │   │
│  │  │   │ SignalWidget │  │ SignalWidget │       │  │   │
│  │  │   └──────────────┘  └──────────────┘       │  │   │
│  │  └────────────────────────────────────────────┘  │   │
│  │  Hotkey strip / status bar                        │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ decoded signal updates
                          │
┌─────────────────────────┴───────────────────────────────┐
│                    Decode Pipeline                       │
│   raw frame  →  canboat decoder  →  signal router        │
│                  (pgns.json)          (PGN+field+src     │
│                                        → signal_id)      │
└─────────────────────────┬───────────────────────────────┘
                          ▲
                          │ N2K frames (in/out)
                          │
┌─────────────────────────┴───────────────────────────────┐
│                       Driver Layer                       │
│   ┌─────────────┐  ┌──────────────┐  ┌──────────────┐   │
│   │ Actisense   │  │ File replay  │  │ (3rd party)  │   │
│   │ NGT-1       │  │ .pgnlog      │  │              │   │
│   └─────────────┘  └──────────────┘  └──────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### Driver interface

A driver is any class implementing:

```python
class Driver(Protocol):
    name: str                         # "actisense-ngt1"
    capabilities: set[Capability]     # {READ, WRITE, REPLAY}

    def open(self, config: dict) -> None: ...
    def close(self) -> None: ...
    def read_frames(self) -> Iterator[Frame]: ...   # blocking generator
    def write_frame(self, frame: Frame) -> None: ... # optional, requires WRITE
```

Drivers are discovered via the `pgntui.drivers` entry point group:

```toml
[project.entry-points."pgntui.drivers"]
actisense-ngt1 = "pgntui_actisense:NGT1Driver"
```

v1 ships with `actisense-ngt1` and `file-replay` built in.

### Decode pipeline

1. Driver yields raw `Frame(timestamp, source_addr, pgn, data_bytes)`
2. Canboat decoder turns the frame into a `{field_name: value}` dict
3. Signal router matches each `(pgn, field, source, instance)` tuple against loaded signal definitions and pushes typed updates to subscribed widgets
4. The router also feeds the Debug tab and (when armed) the recorder

### Containers and widgets

- A **container** is a Textual screen containing a grid of widgets
- A **widget** is a `SignalWidget` subclass — one per signal type (`AnalogIn`, `AnalogOut`, `DigitalIn`, `DigitalOut`)
- Containers are switched via `Tab` / `Shift-Tab` or numeric hotkeys (`1`–`9`)
- Only one container is rendered at a time

## Data model

### Signal JSON

```json
{
  "id": "engine_rpm_port",
  "type": "analog_in",
  "title": "Port Engine RPM",
  "unit": "rpm",
  "pgn": 127488,
  "field": "Engine Speed",
  "source": 0,
  "instance": 0,
  "min": 0,
  "max": 6000,
  "decimals": 0,
  "warn_above": 5500,
  "alarm_above": 5800,
  "smoothing": 0.2,
  "log": true
}
```

Fields by type:

| Field         | analog_in | analog_out | digital_in | digital_out |
|---------------|-----------|------------|------------|-------------|
| `min`/`max`   | required  | required   | —          | —           |
| `unit`        | optional  | optional   | —          | —           |
| `decimals`    | optional  | optional   | —          | —           |
| `warn_*`/`alarm_*` | optional | optional | —     | —           |
| `on_label`/`off_label` | — | —     | optional   | optional    |
| `write_pgn`/`write_field` | — | required | — | required    |
| `smoothing`   | optional  | —          | —          | —           |
| `log`         | optional  | optional   | optional   | optional    |

`smoothing` is an exponential moving average factor `0..1` (0 = no smoothing).

### Container JSON

```json
{
  "id": "engine_room",
  "title": "Engine Room",
  "cols": 12,
  "signals": [
    { "ref": "engine_rpm_port",  "row": 0, "col": 0, "w": 12 },
    { "ref": "engine_rpm_stbd",  "row": 1, "col": 0, "w": 12 },
    { "ref": "oil_pressure",     "row": 2, "col": 0, "w": 6  },
    { "ref": "coolant_temp",     "row": 2, "col": 6, "w": 6  }
  ]
}
```

- `cols` is the grid width (default 12)
- Each signal occupies `w` columns starting at `(row, col)`
- Widget height is fixed (1 row per signal in v1); multi-row widgets reserved for future

### Theme JSON

Themes are JSON files that define colors, glyphs, and box style. Selected via `config.toml`'s `theme = "<name>"`, which resolves to `themes/<name>.json` in the workspace (workspace overrides shipped defaults).

```json
{
  "id": "amber-crt",
  "title": "Amber CRT",
  "colors": {
    "bg":         "#1a0f00",
    "fg":         "#ffb000",
    "fg_dim":     "#7a5400",
    "accent":     "#ffe07a",
    "ok":         "#5cff5c",
    "warn":       "#ffcc33",
    "alarm":      "#ff3030",
    "border":     "#7a5400",
    "title_bg":   "#3a2200",
    "title_fg":   "#ffe07a",
    "bar_track":  "#3a2200",
    "bar_fill":   "#ffb000",
    "bar_warn":   "#ffcc33",
    "bar_alarm":  "#ff3030"
  },
  "glyphs": {
    "bar_left":   "├",
    "bar_right":  "┤",
    "bar_track":  "─",
    "bar_marker": "●",
    "on":         "●",
    "off":        "○",
    "box":        "single"
  },
  "styles": {
    "title":      "bold",
    "value":      "bold",
    "unit":       "dim"
  }
}
```

- `colors`: required keys above. Hex `#rrggbb` or named ANSI (`"bright_yellow"`)
- `glyphs.box`: `single` | `double` | `heavy` | `ascii` (last one for terminals that mangle Unicode)
- `styles`: any of `bold` | `italic` | `dim` | `reverse` | `underline`
- Optional `gradients` block — list of color stops + a target (`bar_fill`, `title_fg`, `border`) for themes like `rainbow-disco`. Animated gradients honor a top-level `"animate": true/false` and `"animate_fps"` (default 4)
- Unknown keys are ignored, so themes can be forward-compatible

**Built-in themes** shipped with v1:
- `dark` — default, matches the opcilloscope reference
- `light`
- `amber-crt` — retro instrument vibe
- `green-phosphor` — old radar/CRT
- `mono-ascii` — for SSH sessions / terminals without Unicode or color
- `rainbow-disco` — chaotic-good. Each container tab gets a different hue, bar fills are gradients across the spectrum, signal titles cycle through the rainbow on a slow timer. Reduced-motion users can set `"animate": false` to freeze the gradients. Not for actual sea use; perfect for demos and parties.

Users drop their own JSON into `~/.config/pgntui/themes/` and `theme = "my-boat"` picks it up.

### App config (`config.toml`)

```toml
[driver]
name = "actisense-ngt1"
port = "/dev/tty.usbserial-FT1234"
baud = 115200

[app]
write_enabled = false
theme = "dark"
workspace = "~/.config/pgntui"

[logging]
csv_dir = "logs"
record_dir = "recordings"
```

## Widget visuals

```
analog_in       Port Engine RPM    ├────────●────────┤   2150 rpm
analog_out      Autopilot Heading  ├──────●──────────┤    142° [set]
digital_in      Bilge Pump         ● ON
digital_out     Anchor Light       [○ OFF]
```

- Bar color tracks `warn_above` / `alarm_above` (green / yellow / red)
- `analog_out` and `digital_out` are dimmed and non-interactive when `write_enabled = false`
- `[set]` opens an inline numeric input; toggles fire on `Space` when focused

## Modes

### Live (default)
Driver streams real frames. All widgets update. Write enabled per config.

### Debug tab
Always present. Shows a scrolling table of decoded frames:

```
Time      Src  Dst  PGN     Name                       Fields
15:42:01  23   255  127488  Engine Parameters Rapid    rpm=2150 boost=12
15:42:01  35   255  130306  Wind Data                  speed=12.4kn angle=42°
```

Hotkeys: pause/resume, filter by PGN, filter by source, toggle raw hex column, clear.

### Record
`R` toggles recording. Captures raw frames to Actisense `.log` format in `recordings/YYYY-MM-DD_HHMM.pgnlog`. Status bar shows `[● REC]  filename  elapsed  frame-count  size`.

### Replay
`pgntui replay <file>` or opened from the `Recordings` tab. Loads the file-replay driver, which feeds the same decode pipeline. Transport bar replaces the hotkey strip:

```
[ ◀◀  ⏸  ▶▶ ]  ├──────●────────────┤  00:01:42 / 00:04:23   Speed: 1x   [Q]uit
```

- Speeds: 0.25x / 0.5x / 1x / 2x / 5x / 10x / max
- Writes hard-disabled regardless of config
- Scrub bar, step frame-by-frame, jump-to-time, bookmark

### CSV logging
Per-signal: signals with `"log": true` append `timestamp,value` to `logs/<signal_id>-YYYY-MM-DD.csv`. Files rotate daily.

## On-disk layout

```
~/.config/pgntui/
├── config.toml
├── signals/
│   ├── engine_rpm_port.json
│   ├── engine_rpm_stbd.json
│   └── ...
├── containers/
│   ├── engine_room.json
│   ├── navigation.json
│   └── helm.json
├── themes/
│   ├── my-boat.json
│   └── ...                  # user themes; built-ins live inside the package
├── logs/
│   └── engine_rpm_port-2026-06-04.csv
└── recordings/
    └── 2026-06-04_1432.pgnlog
```

`--workspace <dir>` overrides the default location, so users can keep one workspace per boat.

## Safety

- Read-only by default. Outputs render dimmed; key events that would write produce a flash + status-bar hint pointing at `--enable-write` / `config.toml`.
- Replay always disables writes.
- Each write action that succeeds is mirrored into the Debug tab and the active recording (if any) for audit.

## Hotkeys (default)

| Key            | Action                              |
|----------------|-------------------------------------|
| `Tab` / `S-Tab`| Next / previous container           |
| `1`..`9`       | Jump to container N                 |
| `D`            | Debug tab                           |
| `R`            | Record toggle                       |
| `Space`        | Toggle focused digital_out / play-pause in replay |
| `Enter`        | Edit focused analog_out             |
| `P`            | Pause Debug stream                  |
| `F`            | Filter Debug stream                 |
| `?`            | Help overlay                        |
| `Q`            | Quit                                |

All hotkeys remappable in `config.toml`.

## Module layout

```
pgntui/
├── pyproject.toml
├── src/pgntui/
│   ├── __main__.py
│   ├── app.py                 # Textual App
│   ├── config.py              # TOML loader, workspace resolution
│   ├── drivers/
│   │   ├── base.py            # Driver Protocol, Capability enum, Frame dataclass
│   │   ├── actisense.py       # NGT-1 driver
│   │   └── replay.py          # File-replay driver
│   ├── decode/
│   │   ├── canboat.py         # canboat pgns.json wrapper
│   │   ├── router.py          # PGN → signal_id matcher
│   │   └── pgns.json          # bundled
│   ├── signals/
│   │   ├── base.py            # Signal dataclasses + JSON loader
│   │   └── widgets.py         # AnalogIn / AnalogOut / DigitalIn / DigitalOut
│   ├── containers/
│   │   ├── loader.py
│   │   └── screen.py          # ContainerScreen
│   ├── themes/
│   │   ├── loader.py          # JSON → Theme dataclass, generates Textual CSS at runtime
│   │   └── builtin/           # dark.json, light.json, amber-crt.json, green-phosphor.json, mono-ascii.json, rainbow-disco.json
│   ├── debug/
│   │   └── tab.py
│   ├── recording/
│   │   ├── writer.py          # Actisense .log writer
│   │   └── reader.py          # used by replay driver
│   └── logging/
│       └── csv.py
├── examples/
│   ├── signals/
│   └── containers/
└── docs/
```

## Testing

- Unit tests for canboat decode against fixture frames
- Unit tests for signal router matching (PGN/field/source/instance combinations)
- Driver tests use the replay driver against fixture `.pgnlog` files
- Textual snapshot tests for each widget type in nominal / warn / alarm / disabled states
- End-to-end: replay a fixture session, assert that container widgets reach expected values

## Distribution

**Repository:** `github.com/phobicdotno/pgntui` — source, releases, issues, CI.

**Primary channel — PyPI** (publisher account: `phobic`, `pypi.org/user/phobic/`):
- `pipx install pgntui` or `uv tool install pgntui` (recommended for CLI tools — isolated venv, CLI on PATH)
- Drivers ship as separate packages under the same account: `pipx inject pgntui pgntui-actisense`
- Built and published from CI on git tag via `pypa/gh-action-pypi-publish` with a PyPI trusted publisher binding to this repo (no API token in CI secrets)

**Convenience channels:**
- **Homebrew** — `brew install phobicdotno/tap/pgntui` via a custom tap repo
- **WinGet** — `winget install pgntui` for Windows users
- **Standalone binaries** — PyInstaller builds a single executable per platform (macOS arm64, macOS x86_64, Linux x86_64, Windows x86_64), attached to each GitHub Release. No Python install required.

**CI pipeline (GitHub Actions):**
1. On push to `main`: lint, type-check, tests on Python 3.11/3.12/3.13 across macOS / Ubuntu / Windows
2. On tag `vX.Y.Z`: build sdist + wheel → publish to PyPI; build standalone binaries → attach to GitHub Release; update Homebrew tap and WinGet manifest

**Versioning:** SemVer, single source of truth in `pyproject.toml`.

## Open questions for later

- Multi-bus support (more than one driver active simultaneously)
- Alarm sounds / push notifications
- SignalK consumer driver
- Web-based config editor that emits the same JSON
- Theme inheritance (`"extends": "dark"`) to override only a few colors
- Per-container theme override
- Live theme reload on file change
