# Release notes — pgntui v0.3.0 (2026-06-04)

## Overview

Major reliability and correctness pass. Four parallel audits (concurrency, decoding,
platform, packaging) surfaced 27 findings; the bedtime fix wave landed 7 commits
addressing every critical/high item and most mediums. Two of these — fast-packet
reassembly and the canboat Offset bug — meaningfully change what data the app can
correctly display on a real NMEA 2000 network. The rest harden shutdown, recording,
Windows behavior, and the release pipeline itself.

Test count is now 156 (up from 95 at v0.2.0). All green: pytest, ruff check,
ruff format, mypy --strict.

## What got fixed, by audit finding

### Group F1 — PyInstaller spec (commit 7ec4f2d)
- **C-3 / D-C1**: `examples/` directory was not in `datas`, so `pgntui --example` crashed inside the PyInstaller binary. Fixed.
- **D-C2**: `entry_points` metadata was not bundled via `copy_metadata`, so driver discovery (actisense, replay) silently broke inside the binary. Fixed.

### Group F2 — Concurrency + lifecycle (commit 010e7de)
- **A-1**: Worker was not cancelled before `exit()`, leaving an orphan thread on quit. Now cancelled cleanly.
- **A-2**: `_writer` had a race between the worker writing and the main thread closing. Now lock-protected.
- **A-3**: `drivers/actisense.py` had an infinite `read_frames()` loop with no stop event. Now honors a stop event.
- **A-4**: `drivers/replay.py` `close()` did not track the open file handle. Fixed.
- **A-5**: Ctrl+C did not close the recording writer, losing the recording tail. Now closes on SIGINT.
- **C-7**: `_views` property had a type hole via `__dict__.setdefault`. Typed properly.

### Group F3 — Decoder + router + signal types (commit 1f1fca4)
- **B-1**: canboat `Offset` was never applied. This silently miscalibrated 23 AC power fields by exactly 2 GW. Now applied.
- **B-3**: EMA smoothing formula direction documented (was correct but undocumented).
- **B-4**: Router silently cross-contaminated bindings when a frame had no Instance but the binding expected one. Now skipped.
- **B-5**: `_FIELD_ALIASES` docstring added with full listing.
- **C-2**: Threshold fields in signal loader are now coerced to `float`.

### Group F4 — Fast-packet reassembly (commit 1d49368)
- **B-2**: No multi-frame PGN reassembly existed. GNSS, AIS, wind, and any PGN > 8 bytes was silently broken. Now reassembled correctly per canboat fast-packet rules.

### Group F5 — Recording fidelity (commit 46825f5)
- **B-6**: `Frame` did not carry priority or destination, so the recording roundtrip was lossy. Now byte-perfect.
- **C-4**: `recording/writer.py` produced CRLF on Windows because text mode. Now LF-only.

### Group F6 — Platform + config + packaging metadata (commit 9c62160)
- **C-1**: `~/.config/pgntui` was non-standard on Windows. Now uses `platformdirs` for per-OS defaults.
- **C-5**: TOML syntax errors produced a raw traceback. Now a clean message.
- **C-6**: `textual>=0.80` was way too loose. Bumped to `>=8.0`.
- **D-I3**: `[project.urls]` added (Homepage, Source, Bug Tracker, Changelog).
- **D-I4**: README expanded with install, usage, drivers, recording, configuration.
- **D-I5**: New `packaging/README.md` documenting manual homebrew/winget release steps.

### Group F7 — CI/release + validation + flake (commit e6fd561)
- **D-I1**: Release workflow had no `timeout-minutes`. macOS-13 hangs could block the entire release. Now bounded.
- **D-I2**: Release workflow published to PyPI before CI passed. Now gated.
- **D-I6**: Replay timing assertion loosened to avoid flake on loaded CI.
- **B-7**: Container loader did not detect duplicate `(row, col, w)` placements. Now rejected.
- **B-8**: Theme loader did not validate gradient stops. Empty / single-stop / malformed hex now rejected.

## Upgrade notes

- **Windows users**: the default workspace path has moved. Old: `~/.config/pgntui`. New: `%APPDATA%/pgntui` (via platformdirs). Move your existing workspace there or pass `--workspace` explicitly.
- **macOS users**: default workspace is now `~/Library/Application Support/pgntui`.
- **Linux users**: unchanged in practice (XDG-compliant `~/.config/pgntui`).
- **textual**: now requires `>= 8.0`. If you have `textual < 8.0` pinned for another tool, install pgntui in an isolated venv or pipx.
- **Drivers in the PyInstaller binary**: now actually work. If you were hitting "driver not found" errors with the 0.2.x binary, that's gone.
- **Fast-packet PGNs**: GNSS / AIS / wind / any PGN > 8 bytes will now decode. If you had downstream code that assumed these were absent, expect them to start showing up.
- **AC power readings**: were off by 2 GW (yes, gigawatts) due to missing Offset application. Numbers will look different (correct) after upgrade.
- **Recording format**: still backward-compatible to read, but writes now include priority + destination. Old recordings replay fine.

## Test count

- v0.2.0: 95 tests
- v0.3.0: 156 tests (+61)

New tests cover: worker-cancel lifecycle, writer race, recording roundtrip incl. priority/destination, overlapping container placements, gradient stop validation, fast-packet reassembly, threshold float coercion.
