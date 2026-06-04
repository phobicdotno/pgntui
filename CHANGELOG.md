# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
