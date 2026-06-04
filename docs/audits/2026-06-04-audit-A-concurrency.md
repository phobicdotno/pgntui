# Audit A: Concurrency + Lifecycle (2026-06-04)
Branch: main @ 1f3795d (v0.2.1)
Auditor: feature-dev:code-reviewer

## Findings

### Finding A-1: Worker thread not cancelled before `self.exit()` — orphaned blocking thread on quit
- **File:** `src/pgntui/app.py:315-323`
- **Severity:** P1
- **What's wrong:** `action_force_quit` calls `self.exit()` without cancelling the `frame_loop` worker first. After the Textual event loop shuts down, the worker thread is still alive blocked inside `NGT1Driver.read_frames()` (loops `while True: byte = self._serial.read(1)` with 0.1s timeout) or inside `_interruptible_sleep` for replay. `call_from_thread` posted by the still-running worker can fire into a dead event loop and raise `RuntimeError`.
- **Repro:** Press Q during active NGT-1 streaming.
- **Fix:** `self.get_worker("frame_loop").cancel()` before `self.exit()`; close the driver via existing `finally` block.

### Finding A-2: `_writer` written by main thread, read by worker thread — unsynchronised access
- **File:** `src/pgntui/app.py:183` (worker reads), `app.py:297-309` (main writes)
- **Severity:** P1
- **What's wrong:** Worker `_handle_frame` reads `self._writer`; `action_toggle_record` writes it from event loop. `_stop_recording` calls `close()` and then sets `_writer=None`. Worker can read non-None, enter `writer.write(frame)`, while main closes the file handle mid-write — produces `ValueError: I/O operation on closed file` swallowed by `except Exception: pass`. Data integrity loss.
- **Repro:** Press R to stop recording while frames arrive rapidly.
- **Fix:** Add `threading.Lock` protecting `_writer`, OR swap order in `_stop_recording`: null `self._writer` first, then close the local reference.

### Finding A-3: `NGT1Driver.read_frames()` infinite loop — no exit mechanism
- **File:** `src/pgntui/drivers/actisense.py:102-117`
- **Severity:** P1
- **What's wrong:** `while True` with `self._serial.read(1)` timeout-and-continue. Textual `Worker.cancel()` on a `thread=True` worker only sets state and joins with timeout — does NOT inject an exception. Loop only exits when `serial.close()` raises `SerialException`. Timing window between `app.run()` returning and `driver.close()` being called can leak serial port on crash.
- **Fix:** Add `_stop: threading.Event` to `NGT1Driver`, check inside loop, set in `close()`.

### Finding A-4: `FileReplayDriver.close()` only nulls `_path`; open file handle untracked
- **File:** `src/pgntui/drivers/replay.py:41-42`
- **Severity:** P2
- **What's wrong:** `read_log` opens via `with` (correct), but if `close()` is called mid-iteration, only `_path = None` runs. Generator file handle stays open until GC. No deterministic flush/close.
- **Fix:** Store generator/handle, explicitly close in `close()`, or add `_stop` event in `_interruptible_sleep`.

### Finding A-5: `ActisenseLogWriter` not closed on Ctrl+C (SIGINT)
- **File:** `src/pgntui/app.py:315-323`, `src/pgntui/__main__.py:239-246`
- **Severity:** P2
- **What's wrong:** `action_force_quit` flushes the writer. Ctrl+C raises `KeyboardInterrupt` past `app.run()`; `main()` `finally` only closes the driver. Recording tail in Python text buffer is lost.
- **Fix:** In `main()` finally OR via `PgntuiApp.shutdown()`, close `app._writer` if non-None.

### Finding A-6: `AnalogInWidget.update_value` — no documented thread-safety contract
- **File:** `src/pgntui/signals/widgets.py:20-28`
- **Severity:** P2 (future-proofing)
- **What's wrong:** Today only called via `call_from_thread`. No assertion or docstring enforces this. A future direct call from a non-UI thread would race the renderer (two STORE_ATTR for `displayed_value` and `state_class`).
- **Fix:** Add docstring requiring UI thread, optional `assert` guard.

### Finding A-7: `_interruptible_sleep` — pause leftover_delay analysis
- **File:** `src/pgntui/drivers/replay.py:52-70`
- **Severity:** P3 — **no fix required**
- **Notes:** `remaining` is preserved correctly across pause cycles; `_paused` is a single bool (GIL-atomic). Worst case: 50ms latency on resume.

## Clean
- `call_from_thread` used correctly for every widget mutation from worker (debug log, widget updates, status)
- `SignalRouter.route` returns frozen `SignalUpdate`; no shared mutable state
- `Signal` subclasses frozen+slots — read-only after construction
- `CSVSignalLogger.log` flushes on every write
- `ActisenseLogWriter.write` only called from worker (single producer)
- `NGT1Driver.close()` / `FileReplayDriver.close()` guard `is not None`
- `_stop_recording` uses try/finally
- `frame_loop` decorated `exclusive=True` — prevents double-open races
- Day-boundary rotation closes stale handles synchronously

## Notes
- `driver.close()` in `main()` finally is the primary backstop; works for normal exit but not `os._exit()`, SIGKILL, hard crash. Acceptable.
- `_set_status` called from both threads — works because event loop calls direct, worker uses `call_from_thread`. Easy to misread during future edits.
- `_make_analog_write` / `_make_digital_write` callbacks invoke `_set_status` directly — fine today since Textual widget callbacks fire on event loop, but unsafe if ever invoked from non-UI context.
