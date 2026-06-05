# pgntui

Cross-platform TUI for NMEA 2000 with canboat decoding.

Read live N2K frames through pluggable drivers, decode them with the
canboat PGN database, and route values into JSON-defined dashboards. Record
sessions to `.pgnlog` and replay them later — no boat required.

## Install

The easiest path is `pipx`:

    pipx install pgntui

Don't have `pipx`? Install it with pip, then make sure it is on PATH:

    python -m pip install --user pipx
    python -m pipx ensurepath

Open a new terminal afterwards so the PATH change takes effect. On
Debian/Ubuntu you can use `sudo apt install pipx` instead, and on macOS
`brew install pipx`.

If your system Python is older than 3.11, point pipx at a newer interpreter:

    pipx install --python python3.12 pgntui

Or run in a project venv:

    python3 -m venv .venv && . .venv/bin/activate
    pip install pgntui

Standalone single-file binaries for macOS (arm64, x86_64), Linux (x86_64) and
Windows (x86_64) are attached to each GitHub release.

## Quickstart

Scaffold the example workspace and launch:

    pgntui --example      # writes the example workspace at the OS default location
    pgntui                # opens the TUI; no driver yet, debug tab will be empty

Replay a recording:

    pgntui replay path/to/session.pgnlog

Run with a real driver — pgntui picks the driver named in `config.toml`:

    pgntui                # uses driver.name from <workspace>/config.toml

## Workspace layout

`pgntui` reads everything from a workspace directory. By default the location
follows `platformdirs.user_config_dir("pgntui")`:

| OS      | Default workspace                          |
|---------|--------------------------------------------|
| Linux   | `~/.config/pgntui`                         |
| macOS   | `~/Library/Application Support/pgntui`     |
| Windows | `%APPDATA%\pgntui`                         |

Override with `--workspace <path>` on the command line.

Layout:

    <workspace>/
      config.toml            # driver + theme + paths
      signals/*.json         # signal definitions (PGN -> field -> widget)
      containers/*.json      # dashboard layouts (tab -> grid of signals)
      recordings/            # .pgnlog files written by the R hotkey
      logs/                  # CSV exports

Run `pgntui --example` to drop a working sample inside this directory.

## Drivers

Built-in driver entry points (`pgntui.drivers`):

- `actisense-ngt1` — Actisense NGT-1 USB serial gateway (`pyserial`)
- `file-replay` — replay an Actisense `.pgnlog` capture

Pick one in `config.toml`:

    [driver]
    name = "actisense-ngt1"
    port = "/dev/tty.usbserial-XXXX"   # macOS / Linux
    # port = "COM4"                    # Windows
    baud = 115200

Third-party drivers can register additional entry points under the
`pgntui.drivers` group.

## Signal types

Signal JSON files declare how each PGN field renders:

- `analog_in` — gauge / numeric readout (RPM, speed, depth, temperature)
- `digital_in` — boolean lamp (alarm, anchor light, bilge pump state)
- `analog_out` — write-back analog control (sends an outbound frame)
- `digital_out` — write-back toggle (sends an outbound frame)

`analog_out` and `digital_out` need `--enable-write` on the CLI **and**
`app.write_enabled = true` in `config.toml`; otherwise they render as
read-only.

## Themes

Six builtins ship in the wheel:

- `dark` (default)
- `light`
- `amber-crt`
- `green-phosphor`
- `mono-ascii`
- `rainbow-disco`

Custom themes are JSON files referenced from `config.toml`:

    [app]
    theme = "dark"

## Replay

Replay an Actisense-format `.pgnlog`:

    pgntui replay capture.pgnlog

The replay driver respects the original frame spacing. Press the `R` hotkey
inside the TUI to start/stop recording the live stream to a new
`.pgnlog` file under `<workspace>/recordings/`.

## Hotkeys

    Tab / Shift+Tab     next / previous container tab
    D                   jump to Debug tab
    R                   start / stop recording
    Q / Ctrl+Q          quit immediately
    ?                   show help line in status bar

## Layout sketch

```
+---------------------------------------------------+
|  pgntui                                           |
+---------------------------------------------------+
| [Main] [Engine] [Nav] [Debug]                     |
+---------------------------------------------------+
|  RPM     1450    Speed   6.8 kn   Depth 12.3 m    |
|  +----+         +----+           +----+           |
|  |####|         |##  |           |#   |           |
|  +----+         +----+           +----+           |
|                                                   |
|  Bilge OFF     Anchor Light ON                    |
+---------------------------------------------------+
| [Tab] Next  [D] Debug  [R] Rec  [Q] Quit          |
| status: idle                                      |
+---------------------------------------------------+
```

## Status

Alpha. Reasonable to dogfood on a known-good boat or a bench rig.

- Works: TUI shell, canboat decoder, signal routing, file replay,
  Actisense NGT-1 driver (read), recording.
- Partial: NGT-1 write-back is wired but field-tested only against a tiny
  PGN subset.
- Not yet: TwoCAN / Yacht Devices native drivers, more layout primitives,
  per-signal alarm thresholds in the UI.

Bug reports and patches welcome — file an issue at
<https://github.com/phobicdotno/pgntui/issues>.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Source: <https://github.com/phobicdotno/pgntui>
- Issues: <https://github.com/phobicdotno/pgntui/issues>
- Releases: <https://github.com/phobicdotno/pgntui/releases>
