# Round 3 Audit (post 0.3.1)
Branch: main @ 71d5f78

## NF-1 + NF-2 Verification

- **NF-1 (reader UTC):** PASS — `recording/reader.py:20` does `.replace(tzinfo=UTC).timestamp()` correctly.
- **NF-1 test:** PASS — `test_recording_roundtrip.py:52-55` asserts `abs(restored.timestamp - written.timestamp) < 1e-3`.
- **NF-2 (polling pause):** PASS — `test_replay_mode.py` budget loop polls with 50ms quantum, fast-fails on leak. Sliding margin 20× test threshold.

## Sweep A — Errors

| Severity | File:line | Issue |
|---|---|---|
| OK | reader.py:27 | `except (ValueError, IndexError)` — line parser, returns None |
| OK | fastpacket.py:158,167 | Skips bad PGN/length entries in pgns.json |
| OK | containers/themes/signals/config loaders | All raise typed exceptions |
| OK | __main__.py:139 | importlib.metadata fallback |
| OK | __main__.py:157 | driver.open exception → stderr + None (correct for optional hardware) |
| OK | app.py:175 | Frame loop safety net logs to UI |
| **SILENT** | **app.py:190** | **`except Exception: pass` on writer.write() — silent drop on disk full or closed file** |
| OK | app.py:273 | Pre-mount _set_status guard |
| OK | app.py:339,349 / __main__.py:250,259 | Defensive teardown finals |

### NF-3 (P3): app.py:190 silent write error
- **What's wrong:** Recording writer.write() error silently swallowed. On full disk or closed file the recording silently stops while UI shows "REC -> filename".
- **Fix:** One-liner — `self.call_from_thread(self._set_status, f"rec error: {e}")` in the except block.

## Sweep B — Resources

- All file handles via `with` blocks or explicit close in finally/close()
- `_writer_lock`, `_stop` Events properly initialized, no deadlock risk
- No subprocess, signal handlers, or fork calls
- `CSVSignalLogger` not currently wired into PgntuiApp (standalone) — no live handle leak

## Sweep C — Public API

- `__init__.py` exports only `__version__`. Minimal.
- entry-points correct: `actisense-ngt1 → NGT1Driver`, `file-replay → FileReplayDriver`. Both verified to exist + implement Driver Protocol.
- Minor: `__main__.py` imports `_default_workspace` (leading-underscore) from config. Convention violation, not functional bug.

## Sweep D — CLI UX

- `--help` documents `--workspace`, `--enable-write`, `--check`, `--example`, `replay` ✓
- `pgntui replay` (no file) → argparse usage error ✓
- `pgntui --example /path/to/file` → `iterdir()` raises `NotADirectoryError` traceback
- `pgntui --workspace /no/such/dir` → silent default config + welcome (reasonable)
- `pgntui replay --help` → argparse subparser help ✓

### NF-4 (P3): __main__.py:59 --example handles file path poorly
- **What's wrong:** `--example` targeting an existing file (not dir) raises `NotADirectoryError` instead of clean message.
- **Fix:** One-liner — `if workspace.is_file(): print("error: workspace path is a file"); return 1` before iterdir.

## Sweep E — Wheel hygiene

Verified via pyproject.toml static analysis (build not run):
- All force-include entries map to real files
- `decode/fastpacket.py` covered by packages=[src/pgntui] auto-discovery ✓
- `examples/__pycache__/` exists on disk (cosmetic; hatchling excludes by default)
- entry_points.txt derived correctly
- [project.urls] complete ✓

## Sweep F — Docs accuracy

- README.md: install, quickstart, workspace, themes, hotkeys, status — all match code ✓
- packaging/README.md: runbook executable; example version `0.2.2` is a template (cosmetic)
- CHANGELOG.md: 0.3.1 + 0.3.0 entries match commits ✓
- release-notes-v0.3.0.md: test count 95→156 accurate ✓

## Verdict

| Round | New P0/P1 | New P2 | New P3 |
|---|---|---|---|
| 1 | 5 | 13 | 12 |
| 2 | 0 | 1 (NF-1) | 1 (NF-2) |
| 3 | 0 | 0 | 2 (NF-3, NF-4) |

**Severity distribution this round: P0=0 P1=0 P2=0 P3=2.**

**Recommendation: STOP.** NF-3 and NF-4 are both edge-case P3s with trivial one-liner fixes. The codebase is clean to leave at 0.3.1, or alternatively ship 0.3.2 with both P3 fixes bundled (~10 min of work). After that, expected diminishing returns from further audit rounds.
