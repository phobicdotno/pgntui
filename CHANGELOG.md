# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.9] — 2026-06-05

### Added
- In-app **Connection** menu (top-bar button or `C` key): choose the serial
  port and speed from dropdowns, **Test** the NGT-1 live (2-second listen with
  a plain-language verdict), **Save** the choice to `config.toml`, or
  **Connect** without restarting.
- `pgntui probe [--port … --baud … --seconds …]` runs the same connection test
  from the command line (port/speed default to `config.toml`).
- `config.write_driver_settings()` persists driver port/speed while preserving
  the file's comments.

## [0.3.8] — 2026-06-05

### Added
- Title bar showing `PgnTui — NMEA 2000 reader — vX.Y.Z`, replacing the
  default `PgntuiApp` header.
- About dialog (top-right **About** button or the `A` key) with a short,
  curated changelog and the running version. `Esc` closes it.

## [0.3.7] — 2026-06-05

### Fixed
- Actisense NGT-1 driver now speaks the real BST serial protocol, verified
  against the canboat actisense-serial reference. Previously it used bare
  `STX`/`ETX` delimiters, escaped the wrong bytes, and built transmit frames
  with the receive-format body under command `0x93` — none of which would
  interoperate with real hardware. Now: `DLE STX`…`DLE ETX` framing,
  DLE-only escaping, correct checksum, `0x94` send command with the
  `priority, PGN, destination, length, data` layout, and a streaming
  reassembler that drops bad-checksum frames. (Field validation pending on
  live hardware.)

### Added
- `pgntui --list-ports` lists available serial ports so you can find the
  NGT-1's COM/tty name. README gains an Actisense NGT-1 setup section.

## [0.3.6] — 2026-06-05

### Added
- Group separators: containers may declare `groups`, rendered as full-width
  themed rule lines (`├── Title ──────┤`) between signal rows.
- JSON library expanded to full NMEA Simulator coverage — four engine
  instances (Main/Stbd/Gen1/Gen2) each with readout/status/transmission,
  batteries Set 1 + Set 2 (instances 0–7), and a second binary switch bank.

### Changed
- Signal rows are now one line tall and pack at the top of the tab
  (`grid-rows: 1`), so dense pages fit on screen.
- Example Nav/Engine tabs regrouped under labelled separators.

### Fixed
- The configured theme now drives Textual's chrome (header, tabs, footer,
  scrollbars), not just widget content — the whole screen is themed instead
  of clashing with Textual's default theme.

## [0.3.5] — 2026-06-05

### Fixed
- Theme colors now actually render on signal widgets. The theme CSS
  classes (`.state-ok`, `.bar-fill`, …) were generated but never applied
  by any widget, so everything except the header drew monochrome.
  Widgets now receive the `Theme` and render Rich text using the theme's
  colors (track/marker/border/value/unit, state colors for warn/alarm)
  and glyphs (`bar_*`, `on`/`off`), so all six builtin themes take
  effect across every tab.

## [0.3.4] — 2026-06-05

### Added
- `scale`/`offset` display transform on `analog_in` signals
  (`shown = decoded * scale + offset`) — canboat decodes SI base units
  (rad, m/s, Pa, K, s); dashboards can now show deg, kn, Bar, mBar, h.
  `min`/`max` and warn/alarm thresholds are in display units.
- `bit` index on `digital_in` signals — binds one flag out of integer
  bitfields such as 127489 Discrete Status 1/2.
- Example workspace: Nav and Engine tabs mirroring the NMEA Simulator
  main panels (heading/deviation/variation, position, SOW/SOG/COG/ROT,
  depth, rudder, wind, current; full 127488/127489 engine readout).
- `library/`: drop-in signal + container JSON sets for 13 simulator
  pages (GPS, Environmental, Boat, Batteries, Engine main/status/
  transmission, Tanks, Binary, DC and Charge, AC, Windlass, Thruster),
  136 signals, all PGN/field bindings validated by tests.

### Fixed
- `speed` and `water_temp` example signals now convert to the kn/°C
  units they always claimed to display.

## [0.3.3] — 2026-06-05

### Fixed
- Container tabs rendered blank: `ContainerView` had no height rule, so the child
  `Grid` (`height: 1fr`) collapsed inside the auto-height parent and every signal
  widget got zero screen area. The view now fills its tab (`height: 1fr`).
  Regression-tested by running the app against the scaffolded example workspace
  and asserting every placed widget occupies non-zero screen area.

## [0.3.2] — 2026-06-04

### Fixed
- Recording writer errors during `_handle_frame` now surface in the status bar instead of being silently swallowed.
- `pgntui --example` targeting an existing file path now prints a clean error instead of a `NotADirectoryError` traceback.

## [0.3.1] — 2026-06-04

### Fixed
- Recording reader now parses timestamps as UTC. Replay frame deltas were unaffected, but CSV export and debug log absolute timestamps were off by the local UTC offset.

### Changed
- `test_iter_frames_honors_pause_with_sliding_resume` now polls instead of hard-sleeping; faster suite, less flake attractor.

## [0.3.0] — 2026-06-04

Bedtime audit fix wave: concurrency, decoding, packaging, recording, platform paths,
validation, and CI gating. Captures audits A/B/C/D from `docs/audits/2026-06-04-*`.

### Added
- Fast-packet reassembly for multi-frame PGNs (GNSS, AIS, wind, etc.).
- Per-OS default workspace via `platformdirs` (Windows %APPDATA%, macOS Application Support, Linux XDG).
- `--check` headless smoke flag and `--example` workspace scaffolder wiring.
- `[project.urls]` (Homepage, Source, Bug Tracker, Changelog) so PyPI page is non-empty.
- Expanded README and new `packaging/README.md` documenting manual homebrew/winget release steps.
- Threshold field float coercion in signal loader.
- Test: worker-cancel-on-quit lifecycle.
- Test: `_writer` race / close-during-write.
- Test: recording byte-perfect roundtrip incl. priority + destination.
- Test: container loader rejects overlapping placements.
- Test: theme loader validates gradient stops (empty / single / malformed hex).

### Fixed
- canboat `Offset` now applied (23 AC power PGN fields were 2 GW off).
- Router no longer silently cross-contaminates when binding expects Instance but frame has none.
- EMA smoothing direction documented (formula clarified vs. standard convention).
- `_writer` race between worker write and main close.
- NGT-1 and replay drivers now honor a stop event instead of looping forever.
- SIGINT (Ctrl+C) closes the recording writer so the tail isn't lost.
- Worker thread is cancelled on app quit instead of being orphaned.
- Recording on Windows no longer emits CRLF (LF-only line endings).
- TOML config syntax errors now surface a clean message instead of a raw traceback.
- PyInstaller spec bundles `examples/` so `--example` works in the binary.
- PyInstaller spec includes `copy_metadata` so `entry_points` (drivers) survive in the binary.

### Changed
- `textual>=8.0` (was `>=0.80`, too loose for actual API usage).
- `Frame` now carries `priority` and `destination` for byte-perfect recording roundtrips.
- Default workspace path moved per OS — see release notes for migration.

### CI / Tooling
- Release workflow now has `timeout-minutes` on every job (macOS-13 hangs no longer block release).
- Release workflow gates PyPI publish behind CI green.
- Replay timing assertion loosened to remove flake risk on loaded CI.

## [0.2.2] — 2026-06-03

### Added
- Example scaffolder includes one of each widget kind (analog_out, digital_in, digital_out).

### Fixed
- `q` now quits immediately.
- Welcome panel shown for empty workspace.
- Visible bottom strips restored.

## [0.2.0] — 2026-06-02

### Added
- Driver → decoder → router → widgets wiring end-to-end.
- ContainerScreen tabs.
- Record toggle.
- `--example` scaffolder.

### Fixed
- Replay `iter_frames` honors paused flag with sliding resume.
- Containers mount widgets before setting `column_span`; expose `widgets` dict.

## [0.1.3] — 2026-06-01

### Added
- `--check` headless flag.
- PgntuiApp wired into CLI.

### Fixed
- EMA smoothing previously stored output as raw, causing exponential lag.

## [0.1.2] — 2026-05-31

### Fixed
- Per-file force-include for theme JSONs in wheel build.
- `[dist]` extras installed for binary builds.

## [0.1.1] — 2026-05-30

Initial published release.

[0.3.2]: https://github.com/phobicdotno/pgntui/releases/tag/v0.3.2
[0.3.1]: https://github.com/phobicdotno/pgntui/releases/tag/v0.3.1
[0.3.0]: https://github.com/phobicdotno/pgntui/releases/tag/v0.3.0
[0.2.2]: https://github.com/phobicdotno/pgntui/releases/tag/v0.2.2
[0.2.0]: https://github.com/phobicdotno/pgntui/releases/tag/v0.2.0
[0.1.3]: https://github.com/phobicdotno/pgntui/releases/tag/v0.1.3
[0.1.2]: https://github.com/phobicdotno/pgntui/releases/tag/v0.1.2
[0.1.1]: https://github.com/phobicdotno/pgntui/releases/tag/v0.1.1
