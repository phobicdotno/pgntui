# Audit B: Decoding + Routing + Signal Math + Themes + Recording (2026-06-04)
Branch: main @ 1f3795d (v0.2.1)
Auditor: feature-dev:code-reviewer

## P1 — wrong output

### B-1: canboat `Offset` never applied — 23 fields silently wrong
- **File:** `src/pgntui/decode/canboat.py:65-93`
- **What's wrong:** `_decode_fields` reads `Resolution` but never `Offset`. Canboat schema is `raw * resolution + offset`. 23 fields in pgns.json carry `"Offset": -2000000000` (AC power PGNs 65007/65008/65009 Real Power, Apparent Power, etc.). Without offset, those decode 2 GW too high.
- **Fix:** `offset_val = float(f.get("Offset") or 0); value = raw * resolution + offset_val`

### B-2: No fast-packet reassembly — multi-frame PGNs silently truncate
- **File:** `src/pgntui/decode/canboat.py:51-63`; no reassembly layer
- **What's wrong:** N2K fast-packet PGNs (129029 GNSS, 129025 Position Rapid, 129026 COG/SOG, 129038/129039 AIS, 130306 Wind Data) arrive as a sequence of 8-byte CAN frames with a sequence counter in byte 0. The decoder parses each 8-byte frame independently. For 43-byte PGN 129029, lat/lon/alt all decode to zero or garbage. No `FastPacketReassembler` exists.
- **Fix:** Add `FastPacketReassembler` keyed by `(source_addr, pgn, sequence_counter)`, strip header bytes, concatenate payload, call `decode()` only when complete.

## P2 — design / semantic flips

### B-3: EMA formula direction inverted relative to standard
- **File:** `src/pgntui/signals/widgets.py:21-23`
- **What's wrong:** Code: `displayed = a * self._raw + (1 - a) * value` where `a = smoothing`. Standard EMA: `ema = alpha * new + (1 - alpha) * old`. With `smoothing=0.9` the display weights 90% old / 10% new — heavily smoothed, but opposite direction from standard `alpha`. The Wave 1 fix test `test_smoothing_ema_uses_raw_not_blended` documents this as intentional (works at alpha=0.5 symmetry point).
- **Fix:** Either rename parameter (`history_weight`?) and document, OR flip the formula to standard EMA. Latter is breaking change. Recommend: document clearly and add a docstring noting the semantic.

### B-4: Router missing-instance allows cross-contamination
- **File:** `src/pgntui/decode/router.py:41`
- **What's wrong:** `if key.instance is not None and instance is not None and key.instance != instance: continue` — short-circuits when frame has no Instance field. A signal keyed to instance 2 receives updates from single-engine PGNs with no instance. Port engine bound to instance 0 gets cross-fire.
- **Fix:** `if key.instance is not None and key.instance != instance: continue` — let None != 2 mismatch.

### B-5: `_FIELD_ALIASES` documentation gap
- **File:** `src/pgntui/decode/canboat.py:24-28`
- **What's wrong:** Alias entries are correct for PGN 127488. But users binding `field: "Speed"` thinking it means PGN 128259 "Speed Water Referenced" will see no match (decoder emits the raw canboat name). Documentation/discoverability problem, not a decoder bug.
- **Fix:** Document the alias table's purpose + how to list canonical field names.

### B-6: Recording priority+destination lossy
- **File:** `src/pgntui/recording/writer.py:31-43`; `src/pgntui/drivers/base.py`
- **What's wrong:** `Frame` has no `priority` or `destination`. Writer hardcodes priority "3", destination "255". No roundtrip test verifies byte-perfect fidelity. Future addressed-PGN routing silently breaks.
- **Fix:** Add optional `priority` + `destination` to Frame dataclass. Update writer/reader. Add roundtrip test.

## P3 — quality

### B-7: Duplicate placement silently passes
- **File:** `src/pgntui/containers/loader.py:43-55`
- **What's wrong:** Two `SignalPlacement` entries with overlapping `(row, col, w)` not detected. UI renders one on top of the other silently.
- **Fix:** Track occupied cells in the validator, raise `ContainerLoadError` on overlap.

### B-8: Theme gradient stops not validated
- **File:** `src/pgntui/themes/loader.py:61-63`
- **What's wrong:** No validation of stop count (0/1) or hex format. Degenerate theme produces render failure at runtime instead of load-time error.
- **Fix:** Validate len(stops) >= 2 and each stop matches `#[0-9a-fA-F]{6}`.

## Clean
- `_read_bits` LSB-first; truncated payload graceful break
- Unknown PGN returns None cleanly
- Signed two's complement correct for any field size
- Resolution=0 guard with 1.0 fallback
- Router source=None wildcard correct; source=0 treated as explicit (correct)
- Router multi-signal routes: `setdefault().append()` accumulates correctly
- AnalogInWidget smoothing=0 path: bypasses EMA correctly
- AnalogInWidget first sample bypasses EMA
- `compute_state` boundary uses `>=` consistently
- DigitalIn/Out truthy cast via `bool(value)` handles 2/-1/"yes"
- `read_log` truncated file: parse returns None, generator skips
- Timestamp precision: microseconds preserved
- Container cols<=0 / neg coords / grid overflow rejected (tested)
- 14 required theme colors validated; all 6 builtin themes complete
- Widget glyphs hardcoded (●─├┤) — missing theme glyph table doesn't break runtime

## Notes
- B-2 (fast-packet) is the biggest production impact — anyone running GNSS/AIS/wind sees broken decodes silently
- B-1 (Offset) only hits AC power; most marine TUI users won't notice
- AnalogInWidget NaN/inf input crashes at `int(NaN * 17)` in `_bar()` — extremely unlikely in real PGN data but worth noting
- `test_recording_writer.py` has no write→read→compare roundtrip — adding one would surface B-6
