# Round 2 Audit (2026-06-04, post fix-wave, pre 0.3.0)
Branch: main @ 010e7de

## Verification Results

All 23 Round 1 findings verified PASS at HEAD.

| Finding | Status | Evidence |
|---|---|---|
| A-1 | PASS | `app.py:346-351` iterates workers, calls `cancel()` on frame_loop group before `exit()` |
| A-2 | PASS | `_writer_lock` guards `_handle_frame` snapshot (185-187) and `_stop_recording` swap (312-314) |
| A-3 | PASS | `actisense.py:122` checks `self._stop.is_set()` at top of `while True` |
| A-4 | PASS | `replay.py:73,79,97,109` — stop event respected in sleep and yield points |
| A-5 | PASS | `__main__.py:255-260` — writer backstop in finally |
| B-1 | PASS | `canboat.py:126-142` applies offset + resolution |
| B-2 | PASS | `canboat.py:66,92` constructs and routes via `FastPacketReassembler` |
| B-4 | PASS | `router.py:44` — None != 2 correctly skips |
| B-6 | PASS | Writer/reader column order match; Frame priority+destination roundtrip |
| B-7 | PASS | `containers/loader.py:45-63` rejects overlap |
| B-8 | PASS | `themes/loader.py:54-61` validates gradient stops |
| C-1 | PASS | `config.py:10` uses platformdirs |
| C-2 | PASS | `signals/base.py:114-117,129-132` coerces thresholds to float |
| C-3 | PASS | `pgntui.spec:9-12` includes examples/ + copy_metadata |
| C-4 | PASS | `writer.py:23` uses `newline=""` |
| C-5 | PASS | `config.py:46-47` catches TOMLDecodeError |
| C-6 | PASS | `pyproject.toml:28` — `textual>=8.0` |
| C-7 | PASS | `app.py:113` — typed `_view_pairs`; no property |
| D-I1 | PASS | release.yml — test:10 / binaries:30 timeouts |
| D-I2 | PASS | pypi + binaries declare `needs: test` |
| D-I3 | PASS | pyproject.toml has [project.urls] |
| D-I4 | PASS | README expanded to 174 lines |
| D-I5 | PASS | packaging/README.md exists with runbook |

## New Findings

### NF-1: Reader parses UTC timestamps as local time
- **File:** `src/pgntui/recording/reader.py:17`
- **Severity:** P2 (replay speed correct via frame deltas; absolute timestamps off by UTC offset)
- **What's wrong:** Writer formats with `tz=UTC`. Reader calls `datetime.strptime(...).timestamp()` on naive datetime, which Python interprets as local time. In UTC+2 every replayed timestamp is 7200s low. CSV export and debug log timestamps are wrong by the local UTC offset.
- **Fix:** `datetime.strptime(parts[0], "%Y-%m-%d-%H:%M:%S.%f").replace(tzinfo=UTC).timestamp()` — one line.

### NF-2: Hard 1.5s sleep in pause test
- **File:** `tests/test_replay_mode.py:95`
- **Severity:** Low (CI flake attractor; no prod impact)
- **What's wrong:** `time.sleep(1.5)` to assert no frames during pause. Accumulates suite time and is fragile under scheduler jitter.
- **Fix:** Replace with polling loop — exit early on `len(emitted) > 1` (fast-fail) capped at a budget.

## Cross-fix Interaction Notes

- **F3 + F4 (Offset + fast-packet):** Clean. `_decode_fields` applies offset on fully assembled payload. No fast-packet PGN in bundled DB has non-zero Offset, but code path is correct regardless.
- **F5 + F2 in actisense.py:** Clean. `_stop` event in `__init__` + read_frames; `parse_frame` returns Frame with priority/destination.
- **F6 + F2 in app.py:** Both present. Welcome text + worker cancel + _writer_lock + atomic swap all in HEAD.
- **F6 + F2 in __main__.py:** Both present. platformdirs config path + TOMLDecodeError catch + SIGINT writer backstop all in HEAD.
- **Writer/reader columns:** `[ts, priority, pgn, src, dst, len, *hex]` — exact alignment.
- **Fast-packet duplicate frame 0 (same seq_id):** Second overwrites buffer with fresh state — N2K retransmit handled.
- **Fast-packet malformed length=0xFF:** Buffer expires via `_expire_stale(5.0s)`. No garbage decode path.
- **FastPacketReassembler thread safety:** Owned by CanboatDecoder, called only from single frame_loop worker. No concurrent access.

## Test Suite

- 156 tests passing
- Real threads in: test_writer_race, test_app_worker_cancel_on_exit, test_replay_mode — all use event-sync or generous-timeout polling except NF-2's flat sleep
- No network, no FS writes outside tmp_path
- No global state mutation; test_fastpacket patches time.monotonic in local context manager
- mypy --strict: clean
- ruff: clean
- No TODO/FIXME/HACK/XXX in src/

## Verdict

**Clean to ship 0.3.0.** All Round 1 findings fixed. NF-1 and NF-2 are minor: reader UTC offset doesn't break replay (frame deltas are correct) and the test sleep is a flake attractor not a prod bug. Fix in 0.3.1.
