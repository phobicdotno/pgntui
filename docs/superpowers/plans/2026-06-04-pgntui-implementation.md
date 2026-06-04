# pgntui Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-platform Textual-based TUI for NMEA 2000 with pluggable drivers (Actisense NGT-1, file replay), canboat decoding, JSON-configured signal widgets and grid containers, record/replay, raw PGN debug tab, per-signal CSV logging, and JSON themes (incl. rainbow-disco).

**Architecture:** Driver layer (Protocol-based, entry_points discovery) → decode pipeline (canboat pgns.json + signal router) → Textual app rendering tabbed grid containers of typed signal widgets. Recording is bus-level (Actisense .log format), replay swaps live driver for file-replay driver. Themes are JSON, resolved to Textual CSS at runtime.

**Tech Stack:** Python 3.11+, Textual, pyserial, canboat pgns.json, TOML config, JSON for signals/containers/themes, pytest, ruff, mypy, uv for packaging, PyInstaller for standalone binaries.

---

## Conventions

- **Project root:** `/Users/phobic/pgntui/`
- **Package root:** `src/pgntui/`
- **Tests root:** `tests/`
- **Fixtures root:** `tests/fixtures/`
- **Python:** 3.11 minimum
- **Lint/format:** `ruff check . && ruff format --check .`
- **Type-check:** `mypy src/pgntui`
- **Tests:** `pytest -q`
- **No emojis in code or commits.**
- **No Co-Authored-By in commits.**
- Run all commands from project root unless otherwise noted.

---

## Task 1 — Repo scaffold

**Create:**
- `/Users/phobic/pgntui/pyproject.toml`
- `/Users/phobic/pgntui/README.md`
- `/Users/phobic/pgntui/LICENSE`
- `/Users/phobic/pgntui/.gitignore`
- `/Users/phobic/pgntui/.github/workflows/ci.yml`
- `/Users/phobic/pgntui/src/pgntui/__init__.py`
- `/Users/phobic/pgntui/src/pgntui/__main__.py`
- `/Users/phobic/pgntui/tests/__init__.py`
- `/Users/phobic/pgntui/tests/test_smoke.py`

- [ ] **Step 1.1: Initialize git repo and write `.gitignore`.**
  ```bash
  cd /Users/phobic/pgntui && git init -b main
  ```
  Write `/Users/phobic/pgntui/.gitignore`:
  ```
  __pycache__/
  *.py[cod]
  .venv/
  .pytest_cache/
  .mypy_cache/
  .ruff_cache/
  dist/
  build/
  *.egg-info/
  .coverage
  htmlcov/
  .DS_Store
  *.spec
  pgntui.bin/
  ```

- [ ] **Step 1.2: Write MIT LICENSE** at `/Users/phobic/pgntui/LICENSE`:
  ```
  MIT License

  Copyright (c) 2026 phobicdotno

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all
  copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.
  ```

- [ ] **Step 1.3: Write `pyproject.toml`** at `/Users/phobic/pgntui/pyproject.toml`:
  ```toml
  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

  [project]
  name = "pgntui"
  version = "0.1.0"
  description = "Cross-platform TUI for NMEA 2000 with canboat decoding and pluggable drivers"
  readme = "README.md"
  requires-python = ">=3.11"
  license = { file = "LICENSE" }
  authors = [{ name = "phobicdotno" }]
  keywords = ["nmea2000", "n2k", "tui", "marine", "canboat"]
  classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console :: Curses",
    "License :: OSI Approved :: MIT License",
    "Operating System :: MacOS",
    "Operating System :: POSIX :: Linux",
    "Operating System :: Microsoft :: Windows",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Terminals",
  ]
  dependencies = [
    "textual>=0.80",
    "pyserial>=3.5",
  ]

  [project.optional-dependencies]
  dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-textual-snapshot>=1.0",
    "ruff>=0.6",
    "mypy>=1.10",
    "pyinstaller>=6.6",
  ]

  [project.scripts]
  pgntui = "pgntui.__main__:main"

  [project.entry-points."pgntui.drivers"]
  actisense-ngt1 = "pgntui.drivers.actisense:NGT1Driver"
  file-replay = "pgntui.drivers.replay:FileReplayDriver"

  [tool.hatch.build.targets.wheel]
  packages = ["src/pgntui"]

  [tool.hatch.build.targets.wheel.force-include]
  "src/pgntui/decode/pgns.json" = "pgntui/decode/pgns.json"

  [tool.ruff]
  line-length = 100
  target-version = "py311"

  [tool.ruff.lint]
  select = ["E", "F", "I", "B", "UP", "N"]

  [tool.mypy]
  python_version = "3.11"
  strict = true
  packages = ["pgntui"]
  mypy_path = "src"

  [tool.pytest.ini_options]
  testpaths = ["tests"]
  asyncio_mode = "auto"
  ```

- [ ] **Step 1.4: Write README stub** at `/Users/phobic/pgntui/README.md`:
  ```markdown
  # pgntui

  Cross-platform terminal UI for NMEA 2000. Pluggable drivers, canboat decoding,
  JSON-configured dashboards, record/replay.

  ## Install

      pipx install pgntui

  ## Run

      pgntui
      pgntui replay path/to/session.pgnlog

  See `docs/superpowers/specs/2026-06-04-pgntui-design.md` for the design.
  ```

- [ ] **Step 1.5: Create package skeleton.** Files:
  - `/Users/phobic/pgntui/src/pgntui/__init__.py`:
    ```python
    """pgntui — NMEA 2000 TUI."""

    __version__ = "0.1.0"
    ```
  - `/Users/phobic/pgntui/src/pgntui/__main__.py`:
    ```python
    """CLI entry point."""


    def main() -> int:
        """Entry point for `pgntui` console script."""
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    ```
  - `/Users/phobic/pgntui/tests/__init__.py`: empty file.
  - `/Users/phobic/pgntui/tests/test_smoke.py`:
    ```python
    from pgntui import __version__


    def test_version() -> None:
        assert __version__ == "0.1.0"


    def test_main_returns_zero() -> None:
        from pgntui.__main__ import main

        assert main() == 0
    ```

- [ ] **Step 1.6: Install dev deps and run smoke test.**
  ```bash
  cd /Users/phobic/pgntui && python -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest -q
  ```
  Expected output (tail): `2 passed`.

- [ ] **Step 1.7: Write GitHub Actions CI skeleton** at `/Users/phobic/pgntui/.github/workflows/ci.yml`:
  ```yaml
  name: ci
  on:
    push:
      branches: [main]
    pull_request:
  jobs:
    test:
      strategy:
        fail-fast: false
        matrix:
          os: [ubuntu-latest, macos-latest, windows-latest]
          python: ["3.11", "3.12", "3.13"]
      runs-on: ${{ matrix.os }}
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with:
            python-version: ${{ matrix.python }}
        - run: pip install -e ".[dev]"
        - run: ruff check .
        - run: ruff format --check .
        - run: mypy src/pgntui
        - run: pytest -q
  ```

- [ ] **Step 1.8: Initial commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "scaffold: pyproject, package skeleton, CI, license"
  ```

---

## Task 2 — Core dataclasses (`Frame`, `Capability`, `Driver` Protocol)

**Create:**
- `/Users/phobic/pgntui/src/pgntui/drivers/__init__.py`
- `/Users/phobic/pgntui/src/pgntui/drivers/base.py`
- `/Users/phobic/pgntui/tests/test_drivers_base.py`

- [ ] **Step 2.1: Write failing test** at `tests/test_drivers_base.py`:
  ```python
  from pgntui.drivers.base import Capability, Frame


  def test_frame_construct_and_repr() -> None:
      f = Frame(timestamp=1.5, source_addr=23, pgn=127488, data=b"\x01\x02\x03")
      assert f.timestamp == 1.5
      assert f.source_addr == 23
      assert f.pgn == 127488
      assert f.data == b"\x01\x02\x03"


  def test_frame_is_immutable() -> None:
      import dataclasses

      f = Frame(timestamp=0.0, source_addr=0, pgn=0, data=b"")
      try:
          f.pgn = 1  # type: ignore[misc]
      except dataclasses.FrozenInstanceError:
          return
      raise AssertionError("Frame must be frozen")


  def test_capability_values() -> None:
      assert {Capability.READ, Capability.WRITE, Capability.REPLAY} == set(Capability)


  def test_driver_protocol_runtime_checkable() -> None:
      from pgntui.drivers.base import Driver

      class Dummy:
          name = "dummy"
          capabilities = {Capability.READ}

          def open(self, config: dict) -> None: ...
          def close(self) -> None: ...
          def read_frames(self):
              yield from ()

          def write_frame(self, frame: Frame) -> None: ...

      assert isinstance(Dummy(), Driver)
  ```

- [ ] **Step 2.2: Run test, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_drivers_base.py -q
  ```
  Expected: `ModuleNotFoundError: No module named 'pgntui.drivers'`.

- [ ] **Step 2.3: Implement** `src/pgntui/drivers/__init__.py` as empty file, then `src/pgntui/drivers/base.py`:
  ```python
  """Driver Protocol, Capability enum, Frame dataclass."""

  from __future__ import annotations

  from collections.abc import Iterator
  from dataclasses import dataclass
  from enum import Enum
  from typing import Protocol, runtime_checkable


  class Capability(Enum):
      READ = "read"
      WRITE = "write"
      REPLAY = "replay"


  @dataclass(frozen=True, slots=True)
  class Frame:
      timestamp: float
      source_addr: int
      pgn: int
      data: bytes


  @runtime_checkable
  class Driver(Protocol):
      name: str
      capabilities: set[Capability]

      def open(self, config: dict) -> None: ...
      def close(self) -> None: ...
      def read_frames(self) -> Iterator[Frame]: ...
      def write_frame(self, frame: Frame) -> None: ...
  ```

- [ ] **Step 2.4: Run test, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_drivers_base.py -q
  ```
  Expected: `4 passed`.

- [ ] **Step 2.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "drivers/base: Frame, Capability, Driver Protocol"
  ```

---

## Task 3 — Canboat integration

**Create:**
- `/Users/phobic/pgntui/src/pgntui/decode/__init__.py`
- `/Users/phobic/pgntui/src/pgntui/decode/canboat.py`
- `/Users/phobic/pgntui/src/pgntui/decode/pgns.json` (bundled — download)
- `/Users/phobic/pgntui/tests/fixtures/__init__.py`
- `/Users/phobic/pgntui/tests/fixtures/frames.py`
- `/Users/phobic/pgntui/tests/test_canboat.py`

- [ ] **Step 3.1: Bundle canboat `pgns.json`.**
  ```bash
  cd /Users/phobic/pgntui && mkdir -p src/pgntui/decode && curl -fsSL -o src/pgntui/decode/pgns.json https://raw.githubusercontent.com/canboat/canboat/master/docs/canboat.json
  ```
  If the URL above is unreachable, fall back to:
  ```bash
  curl -fsSL -o src/pgntui/decode/pgns.json https://raw.githubusercontent.com/canboat/canboat/master/analyzer/pgns.json
  ```
  Verify with `head -c 80 src/pgntui/decode/pgns.json` — expect leading `{` and a `"PGNs"` or `"pgns"` token.

- [ ] **Step 3.2: Write fixture builder** at `tests/fixtures/__init__.py` (empty) and `tests/fixtures/frames.py`:
  ```python
  """Hand-built raw NMEA 2000 frames used in unit tests."""

  from pgntui.drivers.base import Frame

  # PGN 127488 Engine Parameters Rapid Update
  # Byte layout per canboat:
  #   0: instance (uint8)         = 0
  #   1-2: engine speed (uint16 LE, resolution 0.25 rpm) = 2150 rpm -> 8600 -> 0x2198
  #   3-4: boost pressure (uint16 LE, resolution 100 Pa) = 1200 Pa -> 12 -> 0x000C
  #   5: tilt/trim (int8)         = 0
  #   6-7: reserved               = 0xFFFF
  ENGINE_RAPID = Frame(
      timestamp=1700000000.0,
      source_addr=23,
      pgn=127488,
      data=bytes([0x00, 0x98, 0x21, 0x0C, 0x00, 0x00, 0xFF, 0xFF]),
  )
  ```

- [ ] **Step 3.3: Write failing test** at `tests/test_canboat.py`:
  ```python
  from tests.fixtures.frames import ENGINE_RAPID

  from pgntui.decode.canboat import CanboatDecoder, DecodedFrame


  def test_decoder_loads_bundled_pgns() -> None:
      dec = CanboatDecoder.load_bundled()
      assert dec.has_pgn(127488)


  def test_decode_engine_rapid_rpm_units() -> None:
      dec = CanboatDecoder.load_bundled()
      result = dec.decode(ENGINE_RAPID)
      assert isinstance(result, DecodedFrame)
      assert result.pgn == 127488
      assert result.name and "Engine" in result.name
      rpm = result.fields.get("Engine Speed")
      assert rpm is not None
      assert 2140 <= float(rpm) <= 2160


  def test_decode_unknown_pgn_returns_none() -> None:
      from pgntui.drivers.base import Frame

      dec = CanboatDecoder.load_bundled()
      bogus = Frame(timestamp=0.0, source_addr=0, pgn=999999, data=b"\x00")
      assert dec.decode(bogus) is None
  ```

- [ ] **Step 3.4: Run test, confirm failure** (`ModuleNotFoundError`):
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_canboat.py -q
  ```

- [ ] **Step 3.5: Implement** `src/pgntui/decode/__init__.py` as empty file, then `src/pgntui/decode/canboat.py`:
  ```python
  """Thin wrapper around the bundled canboat pgns.json database."""

  from __future__ import annotations

  import json
  import struct
  from dataclasses import dataclass, field
  from importlib import resources
  from typing import Any

  from pgntui.drivers.base import Frame


  @dataclass(frozen=True, slots=True)
  class DecodedFrame:
      timestamp: float
      source_addr: int
      pgn: int
      name: str | None
      fields: dict[str, Any] = field(default_factory=dict)


  class CanboatDecoder:
      def __init__(self, db: dict[str, Any]) -> None:
          self._db = db
          pgn_list = db.get("PGNs") or db.get("pgns") or []
          self._by_pgn: dict[int, list[dict[str, Any]]] = {}
          for entry in pgn_list:
              pgn = int(entry.get("PGN") or entry.get("pgn") or 0)
              if pgn:
                  self._by_pgn.setdefault(pgn, []).append(entry)

      @classmethod
      def load_bundled(cls) -> CanboatDecoder:
          with resources.files("pgntui.decode").joinpath("pgns.json").open(
              "r", encoding="utf-8"
          ) as fh:
              return cls(json.load(fh))

      def has_pgn(self, pgn: int) -> bool:
          return pgn in self._by_pgn

      def decode(self, frame: Frame) -> DecodedFrame | None:
          entries = self._by_pgn.get(frame.pgn)
          if not entries:
              return None
          entry = entries[0]
          fields = self._decode_fields(entry, frame.data)
          return DecodedFrame(
              timestamp=frame.timestamp,
              source_addr=frame.source_addr,
              pgn=frame.pgn,
              name=entry.get("Description") or entry.get("Id"),
              fields=fields,
          )

      def _decode_fields(self, entry: dict[str, Any], data: bytes) -> dict[str, Any]:
          out: dict[str, Any] = {}
          bit_offset = 0
          for f in entry.get("Fields", []) or entry.get("fields", []) or []:
              size = int(f.get("BitLength") or f.get("bitLength") or 0)
              if size <= 0:
                  continue
              name = f.get("Name") or f.get("name") or "?"
              raw = _read_bits(data, bit_offset, size)
              resolution = float(f.get("Resolution") or f.get("resolution") or 1.0) or 1.0
              signed = bool(f.get("Signed") or f.get("signed"))
              if signed and raw >= (1 << (size - 1)):
                  raw -= 1 << size
              value: Any = raw * resolution if resolution != 1.0 else raw
              out[name] = value
              bit_offset += size
          return out


  def _read_bits(data: bytes, offset: int, length: int) -> int:
      result = 0
      for i in range(length):
          bit_index = offset + i
          byte_index = bit_index // 8
          bit_in_byte = bit_index % 8
          if byte_index >= len(data):
              break
          bit = (data[byte_index] >> bit_in_byte) & 1
          result |= bit << i
      return result


  __all__ = ["CanboatDecoder", "DecodedFrame"]
  ```

  Note: `struct` import retained intentionally — leave it in place; subsequent tasks may use it.

- [ ] **Step 3.6: Run test, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_canboat.py -q
  ```
  Expected: `3 passed`. If the canboat schema field names differ (`BitLength` vs `Length`), adjust the field-name fallbacks in `_decode_fields` to match the actual file before continuing.

- [ ] **Step 3.7: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "decode/canboat: bundled pgns.json, decoder wrapper with bit-level reader"
  ```

---

## Task 4 — Signal router

**Create:**
- `/Users/phobic/pgntui/src/pgntui/decode/router.py`
- `/Users/phobic/pgntui/tests/test_router.py`

- [ ] **Step 4.1: Write failing test** at `tests/test_router.py`:
  ```python
  from pgntui.decode.canboat import DecodedFrame
  from pgntui.decode.router import SignalKey, SignalRouter, SignalUpdate


  def test_router_matches_pgn_field_source_instance() -> None:
      router = SignalRouter()
      router.bind("rpm_port", SignalKey(pgn=127488, field="Engine Speed", source=23, instance=0))
      df = DecodedFrame(
          timestamp=1.0,
          source_addr=23,
          pgn=127488,
          name="Engine",
          fields={"Engine Speed": 2150.0, "Instance": 0},
      )
      updates = list(router.route(df))
      assert updates == [SignalUpdate(signal_id="rpm_port", timestamp=1.0, value=2150.0)]


  def test_router_skips_non_matching_source() -> None:
      router = SignalRouter()
      router.bind("rpm_port", SignalKey(pgn=127488, field="Engine Speed", source=23, instance=0))
      df = DecodedFrame(
          timestamp=1.0,
          source_addr=99,
          pgn=127488,
          name="Engine",
          fields={"Engine Speed": 2150.0, "Instance": 0},
      )
      assert list(router.route(df)) == []


  def test_router_multi_source_distinct_signals() -> None:
      router = SignalRouter()
      router.bind("rpm_port", SignalKey(pgn=127488, field="Engine Speed", source=23, instance=0))
      router.bind("rpm_stbd", SignalKey(pgn=127488, field="Engine Speed", source=35, instance=1))
      df1 = DecodedFrame(1.0, 23, 127488, "Engine", {"Engine Speed": 2100.0, "Instance": 0})
      df2 = DecodedFrame(1.0, 35, 127488, "Engine", {"Engine Speed": 2200.0, "Instance": 1})
      ids = [u.signal_id for u in list(router.route(df1)) + list(router.route(df2))]
      assert ids == ["rpm_port", "rpm_stbd"]


  def test_router_source_none_is_wildcard() -> None:
      router = SignalRouter()
      router.bind("rpm_any", SignalKey(pgn=127488, field="Engine Speed", source=None, instance=None))
      df = DecodedFrame(1.0, 99, 127488, "Engine", {"Engine Speed": 2100.0, "Instance": 7})
      assert [u.signal_id for u in router.route(df)] == ["rpm_any"]
  ```

- [ ] **Step 4.2: Run test, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_router.py -q
  ```

- [ ] **Step 4.3: Implement** `src/pgntui/decode/router.py`:
  ```python
  """Signal router — matches decoded frames to user-bound signal ids."""

  from __future__ import annotations

  from collections.abc import Iterator
  from dataclasses import dataclass

  from pgntui.decode.canboat import DecodedFrame


  @dataclass(frozen=True, slots=True)
  class SignalKey:
      pgn: int
      field: str
      source: int | None = None
      instance: int | None = None


  @dataclass(frozen=True, slots=True)
  class SignalUpdate:
      signal_id: str
      timestamp: float
      value: object


  class SignalRouter:
      def __init__(self) -> None:
          self._by_pgn: dict[int, list[tuple[str, SignalKey]]] = {}

      def bind(self, signal_id: str, key: SignalKey) -> None:
          self._by_pgn.setdefault(key.pgn, []).append((signal_id, key))

      def route(self, df: DecodedFrame) -> Iterator[SignalUpdate]:
          bindings = self._by_pgn.get(df.pgn)
          if not bindings:
              return
          instance = df.fields.get("Instance")
          for signal_id, key in bindings:
              if key.source is not None and key.source != df.source_addr:
                  continue
              if key.instance is not None and instance is not None and key.instance != instance:
                  continue
              if key.field not in df.fields:
                  continue
              yield SignalUpdate(
                  signal_id=signal_id,
                  timestamp=df.timestamp,
                  value=df.fields[key.field],
              )


  __all__ = ["SignalKey", "SignalRouter", "SignalUpdate"]
  ```

- [ ] **Step 4.4: Run test, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_router.py -q
  ```
  Expected: `4 passed`.

- [ ] **Step 4.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "decode/router: SignalKey, SignalUpdate, SignalRouter with source+instance matching"
  ```

---

## Task 5 — Signal JSON loader + dataclasses

**Create:**
- `/Users/phobic/pgntui/src/pgntui/signals/__init__.py`
- `/Users/phobic/pgntui/src/pgntui/signals/base.py`
- `/Users/phobic/pgntui/tests/test_signals_base.py`

- [ ] **Step 5.1: Write failing test** at `tests/test_signals_base.py`:
  ```python
  import json
  from pathlib import Path

  import pytest

  from pgntui.signals.base import (
      AnalogIn,
      AnalogOut,
      DigitalIn,
      DigitalOut,
      Signal,
      SignalLoadError,
      load_signal,
      load_signals_dir,
  )


  def _write(tmp: Path, name: str, payload: dict) -> Path:
      p = tmp / name
      p.write_text(json.dumps(payload))
      return p


  def test_load_analog_in(tmp_path: Path) -> None:
      p = _write(
          tmp_path,
          "rpm.json",
          {
              "id": "engine_rpm_port",
              "type": "analog_in",
              "title": "Port RPM",
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
              "smoothing": 0.25,
              "log": True,
          },
      )
      sig = load_signal(p)
      assert isinstance(sig, AnalogIn)
      assert sig.id == "engine_rpm_port"
      assert sig.min == 0
      assert sig.max == 6000
      assert sig.smoothing == 0.25
      assert sig.log is True


  def test_load_analog_out_requires_write_pgn(tmp_path: Path) -> None:
      p = _write(
          tmp_path,
          "ap.json",
          {
              "id": "ap_heading",
              "type": "analog_out",
              "title": "Autopilot Heading",
              "pgn": 65360,
              "field": "Heading",
              "min": 0,
              "max": 359,
              "write_pgn": 65360,
              "write_field": "Heading",
          },
      )
      sig = load_signal(p)
      assert isinstance(sig, AnalogOut)
      assert sig.write_pgn == 65360
      assert sig.write_field == "Heading"


  def test_load_digital_in(tmp_path: Path) -> None:
      p = _write(
          tmp_path,
          "bilge.json",
          {
              "id": "bilge_pump",
              "type": "digital_in",
              "title": "Bilge Pump",
              "pgn": 127501,
              "field": "Indicator1",
              "on_label": "ON",
              "off_label": "OFF",
          },
      )
      sig = load_signal(p)
      assert isinstance(sig, DigitalIn)
      assert sig.on_label == "ON"


  def test_load_digital_out(tmp_path: Path) -> None:
      p = _write(
          tmp_path,
          "anchor.json",
          {
              "id": "anchor_light",
              "type": "digital_out",
              "title": "Anchor Light",
              "pgn": 127502,
              "field": "Indicator1",
              "write_pgn": 127502,
              "write_field": "Indicator1",
          },
      )
      sig = load_signal(p)
      assert isinstance(sig, DigitalOut)
      assert sig.write_pgn == 127502


  def test_load_signal_rejects_unknown_type(tmp_path: Path) -> None:
      p = _write(tmp_path, "bad.json", {"id": "x", "type": "nope", "pgn": 1, "field": "f"})
      with pytest.raises(SignalLoadError):
          load_signal(p)


  def test_analog_out_missing_write_pgn_fails(tmp_path: Path) -> None:
      p = _write(
          tmp_path,
          "ap.json",
          {
              "id": "ap",
              "type": "analog_out",
              "title": "AP",
              "pgn": 1,
              "field": "f",
              "min": 0,
              "max": 1,
          },
      )
      with pytest.raises(SignalLoadError):
          load_signal(p)


  def test_load_signals_dir(tmp_path: Path) -> None:
      _write(
          tmp_path,
          "a.json",
          {
              "id": "a",
              "type": "analog_in",
              "title": "A",
              "pgn": 1,
              "field": "f",
              "min": 0,
              "max": 1,
          },
      )
      _write(
          tmp_path,
          "b.json",
          {
              "id": "b",
              "type": "digital_in",
              "title": "B",
              "pgn": 2,
              "field": "g",
          },
      )
      sigs = load_signals_dir(tmp_path)
      assert {s.id for s in sigs} == {"a", "b"}
      assert all(isinstance(s, Signal) for s in sigs)
  ```

- [ ] **Step 5.2: Run test, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_signals_base.py -q
  ```

- [ ] **Step 5.3: Implement** `src/pgntui/signals/__init__.py` as empty, then `src/pgntui/signals/base.py`:
  ```python
  """Signal dataclasses and JSON loader."""

  from __future__ import annotations

  import json
  from dataclasses import dataclass, field
  from pathlib import Path


  class SignalLoadError(ValueError):
      """Raised when a signal JSON document is invalid."""


  @dataclass(frozen=True, slots=True)
  class Signal:
      id: str
      type: str
      title: str
      pgn: int
      field: str
      source: int | None = None
      instance: int | None = None
      log: bool = False


  @dataclass(frozen=True, slots=True)
  class AnalogIn(Signal):
      unit: str | None = None
      min: float = 0.0
      max: float = 1.0
      decimals: int = 0
      warn_above: float | None = None
      alarm_above: float | None = None
      warn_below: float | None = None
      alarm_below: float | None = None
      smoothing: float = 0.0


  @dataclass(frozen=True, slots=True)
  class AnalogOut(Signal):
      unit: str | None = None
      min: float = 0.0
      max: float = 1.0
      decimals: int = 0
      warn_above: float | None = None
      alarm_above: float | None = None
      warn_below: float | None = None
      alarm_below: float | None = None
      write_pgn: int = 0
      write_field: str = ""


  @dataclass(frozen=True, slots=True)
  class DigitalIn(Signal):
      on_label: str = "ON"
      off_label: str = "OFF"


  @dataclass(frozen=True, slots=True)
  class DigitalOut(Signal):
      on_label: str = "ON"
      off_label: str = "OFF"
      write_pgn: int = 0
      write_field: str = ""


  _COMMON = {"id", "type", "title", "pgn", "field", "source", "instance", "log"}


  def _common(payload: dict) -> dict:
      return {
          "id": payload["id"],
          "type": payload["type"],
          "title": payload["title"],
          "pgn": int(payload["pgn"]),
          "field": payload["field"],
          "source": payload.get("source"),
          "instance": payload.get("instance"),
          "log": bool(payload.get("log", False)),
      }


  def load_signal(path: Path) -> Signal:
      try:
          payload = json.loads(path.read_text())
      except json.JSONDecodeError as e:
          raise SignalLoadError(f"{path}: invalid JSON: {e}") from e
      t = payload.get("type")
      try:
          common = _common(payload)
      except KeyError as e:
          raise SignalLoadError(f"{path}: missing key {e}") from e
      if t == "analog_in":
          return AnalogIn(
              **common,
              unit=payload.get("unit"),
              min=float(payload.get("min", 0.0)),
              max=float(payload.get("max", 1.0)),
              decimals=int(payload.get("decimals", 0)),
              warn_above=payload.get("warn_above"),
              alarm_above=payload.get("alarm_above"),
              warn_below=payload.get("warn_below"),
              alarm_below=payload.get("alarm_below"),
              smoothing=float(payload.get("smoothing", 0.0)),
          )
      if t == "analog_out":
          if "write_pgn" not in payload or "write_field" not in payload:
              raise SignalLoadError(f"{path}: analog_out requires write_pgn + write_field")
          return AnalogOut(
              **common,
              unit=payload.get("unit"),
              min=float(payload.get("min", 0.0)),
              max=float(payload.get("max", 1.0)),
              decimals=int(payload.get("decimals", 0)),
              warn_above=payload.get("warn_above"),
              alarm_above=payload.get("alarm_above"),
              warn_below=payload.get("warn_below"),
              alarm_below=payload.get("alarm_below"),
              write_pgn=int(payload["write_pgn"]),
              write_field=payload["write_field"],
          )
      if t == "digital_in":
          return DigitalIn(
              **common,
              on_label=payload.get("on_label", "ON"),
              off_label=payload.get("off_label", "OFF"),
          )
      if t == "digital_out":
          if "write_pgn" not in payload or "write_field" not in payload:
              raise SignalLoadError(f"{path}: digital_out requires write_pgn + write_field")
          return DigitalOut(
              **common,
              on_label=payload.get("on_label", "ON"),
              off_label=payload.get("off_label", "OFF"),
              write_pgn=int(payload["write_pgn"]),
              write_field=payload["write_field"],
          )
      raise SignalLoadError(f"{path}: unknown signal type {t!r}")


  def load_signals_dir(directory: Path) -> list[Signal]:
      out: list[Signal] = []
      for p in sorted(directory.glob("*.json")):
          out.append(load_signal(p))
      return out


  __all__ = [
      "AnalogIn",
      "AnalogOut",
      "DigitalIn",
      "DigitalOut",
      "Signal",
      "SignalLoadError",
      "load_signal",
      "load_signals_dir",
  ]
  ```

- [ ] **Step 5.4: Run test, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_signals_base.py -q
  ```
  Expected: `7 passed`.

- [ ] **Step 5.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "signals/base: dataclasses for all 4 types + JSON loader with validation"
  ```

---

## Task 6 — Container JSON loader

**Create:**
- `/Users/phobic/pgntui/src/pgntui/containers/__init__.py`
- `/Users/phobic/pgntui/src/pgntui/containers/loader.py`
- `/Users/phobic/pgntui/tests/test_containers_loader.py`

- [ ] **Step 6.1: Write failing test** at `tests/test_containers_loader.py`:
  ```python
  import json
  from pathlib import Path

  import pytest

  from pgntui.containers.loader import (
      Container,
      ContainerLoadError,
      SignalPlacement,
      load_container,
  )


  def _write_container(tmp_path: Path, payload: dict) -> Path:
      p = tmp_path / "c.json"
      p.write_text(json.dumps(payload))
      return p


  def test_load_container_ok(tmp_path: Path) -> None:
      p = _write_container(
          tmp_path,
          {
              "id": "engine_room",
              "title": "Engine Room",
              "cols": 12,
              "signals": [
                  {"ref": "rpm_port", "row": 0, "col": 0, "w": 12},
                  {"ref": "rpm_stbd", "row": 1, "col": 0, "w": 12},
              ],
          },
      )
      c = load_container(p, known_signal_ids={"rpm_port", "rpm_stbd"})
      assert isinstance(c, Container)
      assert c.cols == 12
      assert c.signals == [
          SignalPlacement(ref="rpm_port", row=0, col=0, w=12),
          SignalPlacement(ref="rpm_stbd", row=1, col=0, w=12),
      ]


  def test_unknown_signal_ref_fails(tmp_path: Path) -> None:
      p = _write_container(
          tmp_path,
          {
              "id": "e",
              "title": "E",
              "cols": 12,
              "signals": [{"ref": "ghost", "row": 0, "col": 0, "w": 6}],
          },
      )
      with pytest.raises(ContainerLoadError):
          load_container(p, known_signal_ids=set())


  def test_overflows_grid_fails(tmp_path: Path) -> None:
      p = _write_container(
          tmp_path,
          {
              "id": "e",
              "title": "E",
              "cols": 12,
              "signals": [{"ref": "a", "row": 0, "col": 8, "w": 8}],
          },
      )
      with pytest.raises(ContainerLoadError):
          load_container(p, known_signal_ids={"a"})


  def test_negative_coords_fail(tmp_path: Path) -> None:
      p = _write_container(
          tmp_path,
          {
              "id": "e",
              "title": "E",
              "cols": 12,
              "signals": [{"ref": "a", "row": -1, "col": 0, "w": 4}],
          },
      )
      with pytest.raises(ContainerLoadError):
          load_container(p, known_signal_ids={"a"})
  ```

- [ ] **Step 6.2: Run test, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_containers_loader.py -q
  ```

- [ ] **Step 6.3: Implement** `src/pgntui/containers/__init__.py` as empty, then `src/pgntui/containers/loader.py`:
  ```python
  """Container JSON loader."""

  from __future__ import annotations

  import json
  from dataclasses import dataclass
  from pathlib import Path


  class ContainerLoadError(ValueError):
      """Raised when a container JSON document is invalid."""


  @dataclass(frozen=True, slots=True)
  class SignalPlacement:
      ref: str
      row: int
      col: int
      w: int


  @dataclass(frozen=True, slots=True)
  class Container:
      id: str
      title: str
      cols: int
      signals: list[SignalPlacement]


  def load_container(path: Path, known_signal_ids: set[str]) -> Container:
      try:
          payload = json.loads(path.read_text())
      except json.JSONDecodeError as e:
          raise ContainerLoadError(f"{path}: invalid JSON: {e}") from e
      try:
          cid = payload["id"]
          title = payload["title"]
      except KeyError as e:
          raise ContainerLoadError(f"{path}: missing key {e}") from e
      cols = int(payload.get("cols", 12))
      if cols <= 0:
          raise ContainerLoadError(f"{path}: cols must be positive")
      placements: list[SignalPlacement] = []
      for item in payload.get("signals", []):
          ref = item["ref"]
          if ref not in known_signal_ids:
              raise ContainerLoadError(f"{path}: unknown signal ref {ref!r}")
          row = int(item["row"])
          col = int(item["col"])
          w = int(item["w"])
          if row < 0 or col < 0 or w <= 0:
              raise ContainerLoadError(f"{path}: ref {ref!r} has invalid geometry")
          if col + w > cols:
              raise ContainerLoadError(f"{path}: ref {ref!r} overflows grid (cols={cols})")
          placements.append(SignalPlacement(ref=ref, row=row, col=col, w=w))
      return Container(id=cid, title=title, cols=cols, signals=placements)


  __all__ = ["Container", "ContainerLoadError", "SignalPlacement", "load_container"]
  ```

- [ ] **Step 6.4: Run test, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_containers_loader.py -q
  ```
  Expected: `4 passed`.

- [ ] **Step 6.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "containers/loader: validated grid Container + SignalPlacement"
  ```

---

## Task 7 — Theme JSON loader → Textual CSS generator

**Create:**
- `/Users/phobic/pgntui/src/pgntui/themes/__init__.py`
- `/Users/phobic/pgntui/src/pgntui/themes/loader.py`
- `/Users/phobic/pgntui/src/pgntui/themes/builtin/__init__.py`
- `/Users/phobic/pgntui/src/pgntui/themes/builtin/dark.json` (minimal placeholder, expanded in Task 18)
- `/Users/phobic/pgntui/tests/test_themes_loader.py`

- [ ] **Step 7.1: Write a minimal dark theme stub** at `src/pgntui/themes/builtin/dark.json`:
  ```json
  {
    "id": "dark",
    "title": "Dark",
    "colors": {
      "bg": "#0a0a0a", "fg": "#e0e0e0", "fg_dim": "#707070",
      "accent": "#5cd0ff", "ok": "#5cff5c", "warn": "#ffcc33", "alarm": "#ff3030",
      "border": "#303030", "title_bg": "#1a1a1a", "title_fg": "#e0e0e0",
      "bar_track": "#202020", "bar_fill": "#5cd0ff",
      "bar_warn": "#ffcc33", "bar_alarm": "#ff3030"
    },
    "glyphs": {
      "bar_left": "├", "bar_right": "┤", "bar_track": "─",
      "bar_marker": "●", "on": "●", "off": "○", "box": "single"
    },
    "styles": {"title": "bold", "value": "bold", "unit": "dim"}
  }
  ```
  Also write empty `src/pgntui/themes/__init__.py` and `src/pgntui/themes/builtin/__init__.py`.

  Update `pyproject.toml` `[tool.hatch.build.targets.wheel.force-include]` to include theme JSONs:
  ```toml
  [tool.hatch.build.targets.wheel.force-include]
  "src/pgntui/decode/pgns.json" = "pgntui/decode/pgns.json"
  "src/pgntui/themes/builtin" = "pgntui/themes/builtin"
  ```

- [ ] **Step 7.2: Write failing test** at `tests/test_themes_loader.py`:
  ```python
  import json
  from pathlib import Path

  import pytest

  from pgntui.themes.loader import Theme, ThemeLoadError, load_builtin, load_theme, to_textual_css


  def test_load_builtin_dark() -> None:
      theme = load_builtin("dark")
      assert isinstance(theme, Theme)
      assert theme.id == "dark"
      assert theme.colors["bg"].startswith("#")


  def test_to_textual_css_contains_colors_and_classes() -> None:
      theme = load_builtin("dark")
      css = to_textual_css(theme)
      assert theme.colors["bg"] in css
      assert ".bar-fill" in css
      assert ".bar-warn" in css
      assert ".bar-alarm" in css
      assert ".signal-title" in css


  def test_load_theme_from_path(tmp_path: Path) -> None:
      payload = json.loads(
          (Path(__file__).resolve().parent.parent / "src/pgntui/themes/builtin/dark.json").read_text()
      )
      payload["id"] = "custom"
      payload["title"] = "Custom"
      p = tmp_path / "custom.json"
      p.write_text(json.dumps(payload))
      theme = load_theme(p)
      assert theme.id == "custom"


  def test_missing_required_color_fails(tmp_path: Path) -> None:
      p = tmp_path / "bad.json"
      p.write_text(json.dumps({"id": "bad", "title": "Bad", "colors": {"bg": "#000"}}))
      with pytest.raises(ThemeLoadError):
          load_theme(p)


  def test_gradients_block_round_trips(tmp_path: Path) -> None:
      payload = {
          "id": "rainbow",
          "title": "R",
          "colors": {
              k: "#000000"
              for k in (
                  "bg fg fg_dim accent ok warn alarm border title_bg title_fg "
                  "bar_track bar_fill bar_warn bar_alarm"
              ).split()
          },
          "glyphs": {
              "bar_left": "|", "bar_right": "|", "bar_track": "-",
              "bar_marker": "*", "on": "*", "off": "o", "box": "ascii",
          },
          "styles": {},
          "gradients": [
              {"target": "bar_fill", "stops": ["#ff0000", "#00ff00", "#0000ff"]}
          ],
          "animate": True,
          "animate_fps": 6,
      }
      p = tmp_path / "rainbow.json"
      p.write_text(json.dumps(payload))
      theme = load_theme(p)
      assert theme.animate is True
      assert theme.animate_fps == 6
      assert theme.gradients[0].target == "bar_fill"
      assert theme.gradients[0].stops == ("#ff0000", "#00ff00", "#0000ff")
  ```

- [ ] **Step 7.3: Run test, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_themes_loader.py -q
  ```

- [ ] **Step 7.4: Implement** `src/pgntui/themes/loader.py`:
  ```python
  """Theme JSON loader and Textual CSS generator."""

  from __future__ import annotations

  import json
  from dataclasses import dataclass, field
  from importlib import resources
  from pathlib import Path

  REQUIRED_COLORS = (
      "bg", "fg", "fg_dim", "accent", "ok", "warn", "alarm",
      "border", "title_bg", "title_fg",
      "bar_track", "bar_fill", "bar_warn", "bar_alarm",
  )


  class ThemeLoadError(ValueError):
      """Raised when a theme JSON document is invalid."""


  @dataclass(frozen=True, slots=True)
  class Gradient:
      target: str
      stops: tuple[str, ...]


  @dataclass(frozen=True, slots=True)
  class Theme:
      id: str
      title: str
      colors: dict[str, str]
      glyphs: dict[str, str]
      styles: dict[str, str]
      gradients: tuple[Gradient, ...] = ()
      animate: bool = False
      animate_fps: int = 4


  def _parse(payload: dict, source: str) -> Theme:
      try:
          tid = payload["id"]
          title = payload["title"]
          colors = dict(payload["colors"])
      except KeyError as e:
          raise ThemeLoadError(f"{source}: missing key {e}") from e
      for c in REQUIRED_COLORS:
          if c not in colors:
              raise ThemeLoadError(f"{source}: missing color {c!r}")
      gradients = tuple(
          Gradient(target=g["target"], stops=tuple(g["stops"]))
          for g in payload.get("gradients", [])
      )
      return Theme(
          id=tid,
          title=title,
          colors=colors,
          glyphs=dict(payload.get("glyphs", {})),
          styles=dict(payload.get("styles", {})),
          gradients=gradients,
          animate=bool(payload.get("animate", False)),
          animate_fps=int(payload.get("animate_fps", 4)),
      )


  def load_theme(path: Path) -> Theme:
      try:
          payload = json.loads(path.read_text())
      except json.JSONDecodeError as e:
          raise ThemeLoadError(f"{path}: invalid JSON: {e}") from e
      return _parse(payload, str(path))


  def load_builtin(name: str) -> Theme:
      try:
          with resources.files("pgntui.themes.builtin").joinpath(f"{name}.json").open(
              "r", encoding="utf-8"
          ) as fh:
              payload = json.load(fh)
      except FileNotFoundError as e:
          raise ThemeLoadError(f"builtin theme {name!r} not found") from e
      return _parse(payload, f"builtin:{name}")


  def to_textual_css(theme: Theme) -> str:
      c = theme.colors
      lines = [
          f"Screen {{ background: {c['bg']}; color: {c['fg']}; }}",
          f".signal-title {{ color: {c['title_fg']}; background: {c['title_bg']}; }}",
          f".signal-value {{ color: {c['fg']}; }}",
          f".signal-unit  {{ color: {c['fg_dim']}; }}",
          f".bar-track   {{ color: {c['bar_track']}; }}",
          f".bar-fill    {{ color: {c['bar_fill']}; }}",
          f".bar-warn    {{ color: {c['bar_warn']}; }}",
          f".bar-alarm   {{ color: {c['bar_alarm']}; }}",
          f".border-line {{ color: {c['border']}; }}",
          f".state-ok    {{ color: {c['ok']}; }}",
          f".state-warn  {{ color: {c['warn']}; }}",
          f".state-alarm {{ color: {c['alarm']}; }}",
          f".accent      {{ color: {c['accent']}; }}",
          f".disabled    {{ color: {c['fg_dim']}; }}",
      ]
      return "\n".join(lines) + "\n"


  __all__ = [
      "Gradient",
      "Theme",
      "ThemeLoadError",
      "load_builtin",
      "load_theme",
      "to_textual_css",
  ]
  ```

- [ ] **Step 7.5: Run test, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest tests/test_themes_loader.py -q
  ```
  Expected: `5 passed`.

- [ ] **Step 7.6: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "themes/loader: JSON theme + Textual CSS generator + dark stub"
  ```

---

## Task 8 — Textual app shell

**Create:**
- `/Users/phobic/pgntui/src/pgntui/app.py`
- `/Users/phobic/pgntui/tests/test_app_shell.py`
- `/Users/phobic/pgntui/tests/__snapshots__/` (auto-created by pytest-textual-snapshot)

- [ ] **Step 8.1: Write failing test** at `tests/test_app_shell.py`:
  ```python
  import pytest

  from pgntui.app import PgntuiApp
  from pgntui.themes.loader import load_builtin


  @pytest.mark.asyncio
  async def test_app_starts_and_shows_tabs() -> None:
      app = PgntuiApp(theme=load_builtin("dark"), container_titles=["Engine", "Nav"])
      async with app.run_test() as pilot:
          await pilot.pause()
          assert app.query_one("#tabs")
          assert app.query_one("#status-bar")
          assert app.query_one("#hotkey-strip")


  @pytest.mark.asyncio
  async def test_app_applies_theme_css() -> None:
      theme = load_builtin("dark")
      app = PgntuiApp(theme=theme, container_titles=["Engine"])
      async with app.run_test():
          assert theme.colors["bg"] in app.stylesheet.source["theme"].content
  ```

- [ ] **Step 8.2: Run test, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_app_shell.py -q
  ```

- [ ] **Step 8.3: Implement** `src/pgntui/app.py`:
  ```python
  """Textual app shell — tabs, hotkey strip, status bar."""

  from __future__ import annotations

  from textual.app import App, ComposeResult
  from textual.containers import Horizontal, Vertical
  from textual.widgets import Footer, Label, Static, TabbedContent, TabPane

  from pgntui.themes.loader import Theme, to_textual_css


  class PgntuiApp(App):
      CSS = ""

      BINDINGS = [
          ("tab", "next_container", "Next"),
          ("shift+tab", "prev_container", "Prev"),
          ("d", "show_debug", "Debug"),
          ("r", "toggle_record", "Record"),
          ("q", "quit", "Quit"),
          ("question_mark", "help", "Help"),
      ]

      def __init__(self, theme: Theme, container_titles: list[str]) -> None:
          super().__init__()
          self._theme = theme
          self._container_titles = container_titles

      def on_mount(self) -> None:
          self.stylesheet.add_source(to_textual_css(self._theme), path="theme")
          self.stylesheet.parse()
          self.refresh_css()

      def compose(self) -> ComposeResult:
          with Vertical():
              with TabbedContent(id="tabs"):
                  for title in self._container_titles:
                      with TabPane(title):
                          yield Static(title, classes="signal-title")
                  with TabPane("Debug"):
                      yield Static("debug placeholder")
              yield Static("[Tab] Next [D] Debug [R] Rec [Q] Quit", id="hotkey-strip")
              yield Static("status: idle", id="status-bar")

      def action_next_container(self) -> None:
          tabs = self.query_one(TabbedContent)
          tabs.action_next_tab()

      def action_prev_container(self) -> None:
          tabs = self.query_one(TabbedContent)
          tabs.action_previous_tab()

      def action_show_debug(self) -> None:
          tabs = self.query_one(TabbedContent)
          tabs.active = "tab-" + str(len(self._container_titles) + 1)

      def action_toggle_record(self) -> None:
          status = self.query_one("#status-bar", Static)
          status.update("status: REC")

      def action_help(self) -> None:
          status = self.query_one("#status-bar", Static)
          status.update("help: Tab/D/R/Q")


  __all__ = ["PgntuiApp"]
  ```

  Note: `Horizontal` / `Label` / `Footer` imports retained for future expansion; remove if ruff flags `F401` by gating with `__all__` or actual usage. If lint fails, drop unused imports.

- [ ] **Step 8.4: Run test, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_app_shell.py -q
  ```
  Expected: `2 passed`. If `stylesheet.source` API differs between Textual versions, adjust the assertion to `assert to_textual_css(theme) in app.stylesheet.css_to_html()` or read `app.stylesheet._sources` — pick whichever exposes the registered theme CSS in the installed Textual version.

- [ ] **Step 8.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "app: shell with tabs, hotkey strip, status bar, theme CSS apply"
  ```

---

## Task 9 — Widget implementations

**Create:**
- `/Users/phobic/pgntui/src/pgntui/signals/widgets.py`
- `/Users/phobic/pgntui/tests/test_widgets_analog_in.py`
- `/Users/phobic/pgntui/tests/test_widgets_analog_out.py`
- `/Users/phobic/pgntui/tests/test_widgets_digital_in.py`
- `/Users/phobic/pgntui/tests/test_widgets_digital_out.py`

### 9a — AnalogIn

- [ ] **Step 9a.1: Write failing test** at `tests/test_widgets_analog_in.py`:
  ```python
  import pytest

  from pgntui.signals.base import AnalogIn
  from pgntui.signals.widgets import AnalogInWidget


  def _sig(**kw) -> AnalogIn:
      base = dict(
          id="rpm",
          type="analog_in",
          title="RPM",
          pgn=127488,
          field="Engine Speed",
          unit="rpm",
          min=0.0,
          max=6000.0,
          decimals=0,
          warn_above=5500,
          alarm_above=5800,
      )
      base.update(kw)
      return AnalogIn(**base)


  def test_state_thresholds() -> None:
      w = AnalogInWidget(_sig())
      assert w.compute_state(1000) == "ok"
      assert w.compute_state(5600) == "warn"
      assert w.compute_state(5900) == "alarm"


  def test_smoothing_ema() -> None:
      w = AnalogInWidget(_sig(smoothing=0.5))
      w.update_value(1000)
      w.update_value(2000)
      assert 1400 <= w.displayed_value <= 1600


  @pytest.mark.asyncio
  async def test_render_nominal_snapshot() -> None:
      w = AnalogInWidget(_sig())
      w.update_value(2150)
      assert "RPM" in w.render_text()
      assert "2150" in w.render_text()


  @pytest.mark.asyncio
  async def test_render_alarm_marks_state() -> None:
      w = AnalogInWidget(_sig())
      w.update_value(5900)
      assert "alarm" in w.state_class
  ```

- [ ] **Step 9a.2: Run, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_widgets_analog_in.py -q
  ```

- [ ] **Step 9a.3: Implement** the AnalogInWidget portion of `src/pgntui/signals/widgets.py`:
  ```python
  """Textual signal widgets — AnalogIn, AnalogOut, DigitalIn, DigitalOut."""

  from __future__ import annotations

  from textual.widget import Widget

  from pgntui.signals.base import AnalogIn, AnalogOut, DigitalIn, DigitalOut


  class AnalogInWidget(Widget):
      def __init__(self, signal: AnalogIn) -> None:
          super().__init__()
          self.signal = signal
          self.displayed_value: float = signal.min
          self._raw: float | None = None
          self.state_class: str = "state-ok"

      def update_value(self, value: float) -> None:
          if self.signal.smoothing > 0 and self._raw is not None:
              a = self.signal.smoothing
              self.displayed_value = a * self._raw + (1 - a) * value
          else:
              self.displayed_value = float(value)
          self._raw = self.displayed_value
          self.state_class = f"state-{self.compute_state(self.displayed_value)}"
          self.refresh()

      def compute_state(self, v: float) -> str:
          s = self.signal
          if s.alarm_above is not None and v >= s.alarm_above:
              return "alarm"
          if s.warn_above is not None and v >= s.warn_above:
              return "warn"
          if s.alarm_below is not None and v <= s.alarm_below:
              return "alarm"
          if s.warn_below is not None and v <= s.warn_below:
              return "warn"
          return "ok"

      def render_text(self) -> str:
          s = self.signal
          unit = f" {s.unit}" if s.unit else ""
          val = f"{self.displayed_value:.{s.decimals}f}"
          bar = self._bar()
          return f"{s.title:20s} {bar} {val}{unit}"

      def _bar(self) -> str:
          width = 18
          span = max(self.signal.max - self.signal.min, 1e-6)
          pct = (self.displayed_value - self.signal.min) / span
          pct = max(0.0, min(1.0, pct))
          marker_at = int(pct * (width - 1))
          inner = "".join("●" if i == marker_at else "─" for i in range(width))
          return f"├{inner}┤"

      def render(self):
          return self.render_text()
  ```

- [ ] **Step 9a.4: Run, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_widgets_analog_in.py -q
  ```
  Expected: `4 passed`.

- [ ] **Step 9a.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "widgets: AnalogIn with EMA smoothing, threshold colors, bar render"
  ```

### 9b — AnalogOut

- [ ] **Step 9b.1: Write failing test** at `tests/test_widgets_analog_out.py`:
  ```python
  import pytest

  from pgntui.signals.base import AnalogOut
  from pgntui.signals.widgets import AnalogOutWidget


  def _sig() -> AnalogOut:
      return AnalogOut(
          id="ap", type="analog_out", title="AP Heading",
          pgn=65360, field="Heading",
          unit="deg", min=0.0, max=359.0, decimals=0,
          write_pgn=65360, write_field="Heading",
      )


  def test_disabled_when_write_disabled() -> None:
      w = AnalogOutWidget(_sig(), write_enabled=False)
      assert w.is_disabled
      assert "[set]" not in w.render_text()


  def test_enabled_shows_set() -> None:
      w = AnalogOutWidget(_sig(), write_enabled=True)
      assert not w.is_disabled
      assert "[set]" in w.render_text()


  @pytest.mark.asyncio
  async def test_set_dialog_submits_value() -> None:
      w = AnalogOutWidget(_sig(), write_enabled=True)
      pending: list[float] = []
      w.on_write = pending.append
      w.submit_set(142.0)
      assert pending == [142.0]
  ```

- [ ] **Step 9b.2: Run, confirm failure.** Append `AnalogOutWidget` to `src/pgntui/signals/widgets.py`:
  ```python
  class AnalogOutWidget(Widget):
      def __init__(self, signal: AnalogOut, write_enabled: bool = False) -> None:
          super().__init__()
          self.signal = signal
          self.write_enabled = write_enabled
          self.value: float = signal.min
          self.on_write = None  # type: ignore[assignment]

      @property
      def is_disabled(self) -> bool:
          return not self.write_enabled

      def submit_set(self, value: float) -> None:
          if not self.write_enabled:
              return
          self.value = float(value)
          if callable(self.on_write):
              self.on_write(self.value)
          self.refresh()

      def render_text(self) -> str:
          s = self.signal
          unit = f" {s.unit}" if s.unit else ""
          val = f"{self.value:.{s.decimals}f}"
          tail = "[set]" if self.write_enabled else "[disabled]"
          return f"{s.title:20s} {val}{unit} {tail}"

      def render(self):
          return self.render_text()
  ```

- [ ] **Step 9b.3: Run, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_widgets_analog_out.py -q
  ```
  Expected: `3 passed`.

- [ ] **Step 9b.4: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "widgets: AnalogOut with write-enable gate + set dialog hook"
  ```

### 9c — DigitalIn

- [ ] **Step 9c.1: Write failing test** at `tests/test_widgets_digital_in.py`:
  ```python
  from pgntui.signals.base import DigitalIn
  from pgntui.signals.widgets import DigitalInWidget


  def _sig() -> DigitalIn:
      return DigitalIn(
          id="bilge", type="digital_in", title="Bilge",
          pgn=127501, field="Indicator1",
          on_label="ON", off_label="OFF",
      )


  def test_off_state() -> None:
      w = DigitalInWidget(_sig())
      w.update_value(False)
      assert "OFF" in w.render_text()
      assert "○" in w.render_text()


  def test_on_state() -> None:
      w = DigitalInWidget(_sig())
      w.update_value(True)
      assert "ON" in w.render_text()
      assert "●" in w.render_text()
  ```

  Append to `widgets.py`:
  ```python
  class DigitalInWidget(Widget):
      def __init__(self, signal: DigitalIn) -> None:
          super().__init__()
          self.signal = signal
          self.value: bool = False

      def update_value(self, value: bool) -> None:
          self.value = bool(value)
          self.refresh()

      def render_text(self) -> str:
          s = self.signal
          glyph = "●" if self.value else "○"
          label = s.on_label if self.value else s.off_label
          return f"{s.title:20s} {glyph} {label}"

      def render(self):
          return self.render_text()
  ```

- [ ] **Step 9c.2: Run, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_widgets_digital_in.py -q
  ```
  Expected: `2 passed`.

- [ ] **Step 9c.3: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "widgets: DigitalIn with on/off glyph + label"
  ```

### 9d — DigitalOut

- [ ] **Step 9d.1: Write failing test** at `tests/test_widgets_digital_out.py`:
  ```python
  from pgntui.signals.base import DigitalOut
  from pgntui.signals.widgets import DigitalOutWidget


  def _sig() -> DigitalOut:
      return DigitalOut(
          id="anchor", type="digital_out", title="Anchor Light",
          pgn=127502, field="Indicator1",
          on_label="ON", off_label="OFF",
          write_pgn=127502, write_field="Indicator1",
      )


  def test_disabled_when_write_disabled() -> None:
      w = DigitalOutWidget(_sig(), write_enabled=False)
      assert w.is_disabled
      w.toggle()
      assert w.value is False


  def test_toggle_when_enabled() -> None:
      w = DigitalOutWidget(_sig(), write_enabled=True)
      pending: list[bool] = []
      w.on_write = pending.append
      w.toggle()
      assert w.value is True
      assert pending == [True]
      w.toggle()
      assert pending == [True, False]


  def test_render_includes_state_brackets() -> None:
      w = DigitalOutWidget(_sig(), write_enabled=True)
      assert "[○ OFF]" in w.render_text()
      w.toggle()
      assert "[● ON]" in w.render_text()
  ```

  Append to `widgets.py`:
  ```python
  class DigitalOutWidget(Widget):
      def __init__(self, signal: DigitalOut, write_enabled: bool = False) -> None:
          super().__init__()
          self.signal = signal
          self.write_enabled = write_enabled
          self.value: bool = False
          self.on_write = None  # type: ignore[assignment]

      @property
      def is_disabled(self) -> bool:
          return not self.write_enabled

      def toggle(self) -> None:
          if not self.write_enabled:
              return
          self.value = not self.value
          if callable(self.on_write):
              self.on_write(self.value)
          self.refresh()

      def render_text(self) -> str:
          s = self.signal
          glyph = "●" if self.value else "○"
          label = s.on_label if self.value else s.off_label
          return f"{s.title:20s} [{glyph} {label}]"

      def render(self):
          return self.render_text()
  ```

- [ ] **Step 9d.2: Run, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_widgets_digital_out.py -q
  ```
  Expected: `3 passed`.

- [ ] **Step 9d.3: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "widgets: DigitalOut toggle + write-enable gate"
  ```

---

## Task 10 — Container screen renders grid

**Create:**
- `/Users/phobic/pgntui/src/pgntui/containers/screen.py`
- `/Users/phobic/pgntui/tests/test_container_screen.py`

- [ ] **Step 10.1: Write failing test** at `tests/test_container_screen.py`:
  ```python
  import pytest

  from pgntui.containers.loader import Container, SignalPlacement
  from pgntui.containers.screen import ContainerScreen
  from pgntui.signals.base import AnalogIn


  def _sigs() -> dict:
      return {
          "rpm_port": AnalogIn(id="rpm_port", type="analog_in", title="Port RPM",
              pgn=127488, field="Engine Speed", min=0, max=6000),
          "rpm_stbd": AnalogIn(id="rpm_stbd", type="analog_in", title="Stbd RPM",
              pgn=127488, field="Engine Speed", min=0, max=6000),
      }


  @pytest.mark.asyncio
  async def test_screen_mounts_one_widget_per_placement() -> None:
      c = Container(id="er", title="ER", cols=12, signals=[
          SignalPlacement(ref="rpm_port", row=0, col=0, w=12),
          SignalPlacement(ref="rpm_stbd", row=1, col=0, w=12),
      ])
      screen = ContainerScreen(container=c, signals=_sigs(), write_enabled=False)
      from textual.app import App

      class Host(App):
          def on_mount(self):
              self.push_screen(screen)

      app = Host()
      async with app.run_test() as pilot:
          await pilot.pause()
          assert len(list(screen.widgets.values())) == 2
  ```

- [ ] **Step 10.2: Run, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_container_screen.py -q
  ```

- [ ] **Step 10.3: Implement** `src/pgntui/containers/screen.py`:
  ```python
  """ContainerScreen — renders a Container's grid of signal widgets."""

  from __future__ import annotations

  from textual.containers import Grid
  from textual.screen import Screen
  from textual.widget import Widget

  from pgntui.containers.loader import Container
  from pgntui.signals.base import AnalogIn, AnalogOut, DigitalIn, DigitalOut, Signal
  from pgntui.signals.widgets import (
      AnalogInWidget,
      AnalogOutWidget,
      DigitalInWidget,
      DigitalOutWidget,
  )


  class ContainerScreen(Screen):
      def __init__(
          self,
          container: Container,
          signals: dict[str, Signal],
          write_enabled: bool,
      ) -> None:
          super().__init__()
          self.container_def = container
          self.signals = signals
          self.write_enabled = write_enabled
          self.widgets: dict[str, Widget] = {}

      def compose(self):
          grid = Grid(id="container-grid")
          grid.styles.grid_size_columns = self.container_def.cols
          for placement in self.container_def.signals:
              sig = self.signals[placement.ref]
              w = self._make_widget(sig)
              w.styles.column_span = placement.w
              self.widgets[placement.ref] = w
          yield grid

      def on_mount(self) -> None:
          grid = self.query_one(Grid)
          for w in self.widgets.values():
              grid.mount(w)

      def _make_widget(self, sig: Signal) -> Widget:
          if isinstance(sig, AnalogIn):
              return AnalogInWidget(sig)
          if isinstance(sig, AnalogOut):
              return AnalogOutWidget(sig, write_enabled=self.write_enabled)
          if isinstance(sig, DigitalIn):
              return DigitalInWidget(sig)
          if isinstance(sig, DigitalOut):
              return DigitalOutWidget(sig, write_enabled=self.write_enabled)
          raise TypeError(f"Unknown signal type: {type(sig).__name__}")


  __all__ = ["ContainerScreen"]
  ```

- [ ] **Step 10.4: Run, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_container_screen.py -q
  ```
  Expected: `1 passed`.

- [ ] **Step 10.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "containers/screen: ContainerScreen mounts grid of signal widgets"
  ```

---

## Task 11 — File-replay driver

**Create:**
- `/Users/phobic/pgntui/src/pgntui/drivers/replay.py`
- `/Users/phobic/pgntui/src/pgntui/recording/__init__.py`
- `/Users/phobic/pgntui/src/pgntui/recording/reader.py`
- `/Users/phobic/pgntui/tests/fixtures/sample.pgnlog`
- `/Users/phobic/pgntui/tests/test_replay_driver.py`

- [ ] **Step 11.1: Write fixture** at `tests/fixtures/sample.pgnlog` (Actisense ASCII `.log` format: `timestamp,prio,pgn,src,dst,len,b0,b1,...`):
  ```
  2026-06-04-15:42:01.000,2,127488,23,255,8,00,98,21,0c,00,00,ff,ff
  2026-06-04-15:42:01.500,2,127488,23,255,8,00,d0,22,0c,00,00,ff,ff
  2026-06-04-15:42:02.000,3,130306,35,255,8,fa,a8,01,b4,00,00,fa,ff
  ```

- [ ] **Step 11.2: Write failing test** at `tests/test_replay_driver.py`:
  ```python
  from pathlib import Path

  from pgntui.drivers.base import Capability
  from pgntui.drivers.replay import FileReplayDriver


  FIXTURE = Path(__file__).parent / "fixtures" / "sample.pgnlog"


  def test_capabilities() -> None:
      d = FileReplayDriver()
      assert Capability.READ in d.capabilities
      assert Capability.REPLAY in d.capabilities
      assert Capability.WRITE not in d.capabilities


  def test_yields_frames_in_order() -> None:
      d = FileReplayDriver()
      d.open({"path": str(FIXTURE), "speed": "max"})
      frames = list(d.read_frames())
      d.close()
      assert len(frames) == 3
      assert frames[0].pgn == 127488
      assert frames[0].source_addr == 23
      assert frames[2].pgn == 130306
      assert frames[0].data[1] == 0x98


  def test_speed_max_does_not_sleep() -> None:
      import time

      d = FileReplayDriver()
      d.open({"path": str(FIXTURE), "speed": "max"})
      t0 = time.monotonic()
      list(d.read_frames())
      d.close()
      assert time.monotonic() - t0 < 0.5
  ```

- [ ] **Step 11.3: Implement** `src/pgntui/recording/__init__.py` empty, then `src/pgntui/recording/reader.py`:
  ```python
  """Actisense ASCII .log reader."""

  from __future__ import annotations

  from collections.abc import Iterator
  from datetime import datetime
  from pathlib import Path

  from pgntui.drivers.base import Frame


  def parse_line(line: str) -> Frame | None:
      parts = line.strip().split(",")
      if len(parts) < 7:
          return None
      try:
          ts = datetime.strptime(parts[0], "%Y-%m-%d-%H:%M:%S.%f").timestamp()
          pgn = int(parts[2])
          src = int(parts[3])
          length = int(parts[5])
          data = bytes(int(b, 16) for b in parts[6 : 6 + length])
      except (ValueError, IndexError):
          return None
      return Frame(timestamp=ts, source_addr=src, pgn=pgn, data=data)


  def read_log(path: Path) -> Iterator[Frame]:
      with path.open("r", encoding="utf-8") as fh:
          for line in fh:
              if not line.strip() or line.startswith("#"):
                  continue
              frame = parse_line(line)
              if frame is not None:
                  yield frame


  __all__ = ["parse_line", "read_log"]
  ```

  Then `src/pgntui/drivers/replay.py`:
  ```python
  """File-replay driver — feeds .pgnlog frames through the decode pipeline."""

  from __future__ import annotations

  import time
  from collections.abc import Iterator
  from pathlib import Path

  from pgntui.drivers.base import Capability, Frame
  from pgntui.recording.reader import read_log

  _SPEED_MAP = {
      "0.25x": 0.25, "0.5x": 0.5, "1x": 1.0, "2x": 2.0,
      "5x": 5.0, "10x": 10.0, "max": float("inf"),
  }


  class FileReplayDriver:
      name = "file-replay"
      capabilities = {Capability.READ, Capability.REPLAY}

      def __init__(self) -> None:
          self._path: Path | None = None
          self._speed: float = float("inf")

      def open(self, config: dict) -> None:
          self._path = Path(config["path"])
          self._speed = _SPEED_MAP.get(config.get("speed", "max"), float("inf"))

      def close(self) -> None:
          self._path = None

      def read_frames(self) -> Iterator[Frame]:
          if self._path is None:
              return
          prev_ts: float | None = None
          for frame in read_log(self._path):
              if self._speed != float("inf") and prev_ts is not None:
                  dt = (frame.timestamp - prev_ts) / self._speed
                  if dt > 0:
                      time.sleep(dt)
              prev_ts = frame.timestamp
              yield frame

      def write_frame(self, frame: Frame) -> None:
          raise NotImplementedError("replay driver is read-only")


  __all__ = ["FileReplayDriver"]
  ```

- [ ] **Step 11.4: Run, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_replay_driver.py -q
  ```
  Expected: `3 passed`.

- [ ] **Step 11.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "drivers/replay: file-replay driver + Actisense .log reader"
  ```

---

## Task 12 — Actisense NGT-1 driver

**Create:**
- `/Users/phobic/pgntui/src/pgntui/drivers/actisense.py`
- `/Users/phobic/pgntui/tests/test_actisense_driver.py`

NGT-1 framing recap: each binary frame is bracketed by `STX (0x02)` / `ETX (0x03)`, escape byte is `DLE (0x10)` — any data byte equal to `STX`, `ETX`, or `DLE` is prefixed with `DLE` (`0x10`). Frame body: `[cmd:u8][len:u8][payload...][checksum:u8]` where checksum makes the byte sum (cmd + len + payload + checksum) ≡ 0 mod 256. Received N2K message payload layout for cmd `0x93`: `[prio:u8][pgn:u24 little-endian][dst:u8][src:u8][timestamp:u32 LE ms][len:u8][data...]`.

- [ ] **Step 12.1: Write failing test** at `tests/test_actisense_driver.py`:
  ```python
  from unittest.mock import MagicMock

  import pytest

  from pgntui.drivers.actisense import (
      DLE,
      ETX,
      NGT1Driver,
      STX,
      build_n2k_message,
      escape_frame,
      parse_frame,
      unescape_frame,
  )
  from pgntui.drivers.base import Capability, Frame


  def test_capabilities() -> None:
      d = NGT1Driver()
      assert {Capability.READ, Capability.WRITE} <= d.capabilities


  def test_escape_unescape_roundtrip() -> None:
      payload = bytes([0x10, 0x02, 0x03, 0xAA])
      escaped = escape_frame(payload)
      assert escaped.count(DLE) == 4  # 3 escapes + framing-internal DLEs preserved
      assert unescape_frame(escaped) == payload


  def test_parse_frame_pgn_127488() -> None:
      data = bytes([0x00, 0x98, 0x21, 0x0C, 0x00, 0x00, 0xFF, 0xFF])
      msg = build_n2k_message(prio=2, pgn=127488, dst=255, src=23, data=data)
      frame = bytes([STX]) + escape_frame(msg) + bytes([ETX])
      parsed = parse_frame(frame)
      assert isinstance(parsed, Frame)
      assert parsed.pgn == 127488
      assert parsed.source_addr == 23
      assert parsed.data == data


  def test_write_frame_sends_serial() -> None:
      d = NGT1Driver()
      d._serial = MagicMock()  # bypass open()
      d.capabilities = {Capability.READ, Capability.WRITE}
      f = Frame(timestamp=0.0, source_addr=42, pgn=127488, data=b"\x00" * 8)
      d.write_frame(f)
      written = d._serial.write.call_args[0][0]
      assert written[0] == STX
      assert written[-1] == ETX
  ```

- [ ] **Step 12.2: Run, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_actisense_driver.py -q
  ```

- [ ] **Step 12.3: Implement** `src/pgntui/drivers/actisense.py`:
  ```python
  """Actisense NGT-1 driver."""

  from __future__ import annotations

  from collections.abc import Iterator
  from typing import Any

  from pgntui.drivers.base import Capability, Frame

  STX = 0x02
  ETX = 0x03
  DLE = 0x10
  CMD_N2K_MSG = 0x93


  def escape_frame(payload: bytes) -> bytes:
      out = bytearray()
      for b in payload:
          if b in (STX, ETX, DLE):
              out.append(DLE)
          out.append(b)
      return bytes(out)


  def unescape_frame(payload: bytes) -> bytes:
      out = bytearray()
      i = 0
      while i < len(payload):
          if payload[i] == DLE and i + 1 < len(payload):
              out.append(payload[i + 1])
              i += 2
          else:
              out.append(payload[i])
              i += 1
      return bytes(out)


  def _checksum(buf: bytes) -> int:
      return (256 - (sum(buf) & 0xFF)) & 0xFF


  def build_n2k_message(prio: int, pgn: int, dst: int, src: int, data: bytes) -> bytes:
      body = bytearray()
      body.append(prio & 0xFF)
      body.append(pgn & 0xFF)
      body.append((pgn >> 8) & 0xFF)
      body.append((pgn >> 16) & 0xFF)
      body.append(dst & 0xFF)
      body.append(src & 0xFF)
      body += (0).to_bytes(4, "little")  # timestamp
      body.append(len(data))
      body += data
      framed = bytearray([CMD_N2K_MSG, len(body)]) + body
      framed.append(_checksum(framed))
      return bytes(framed)


  def parse_frame(raw: bytes) -> Frame | None:
      if len(raw) < 4 or raw[0] != STX or raw[-1] != ETX:
          return None
      inner = unescape_frame(raw[1:-1])
      if len(inner) < 3:
          return None
      cmd = inner[0]
      length = inner[1]
      body = inner[2 : 2 + length]
      if cmd != CMD_N2K_MSG or len(body) < 11:
          return None
      pgn = body[1] | (body[2] << 8) | (body[3] << 16)
      dst = body[4]
      src = body[5]
      ts_ms = int.from_bytes(body[6:10], "little")
      data_len = body[10]
      data = bytes(body[11 : 11 + data_len])
      return Frame(timestamp=ts_ms / 1000.0, source_addr=src, pgn=pgn, data=data)


  class NGT1Driver:
      name = "actisense-ngt1"
      capabilities = {Capability.READ, Capability.WRITE}

      def __init__(self) -> None:
          self._serial: Any = None

      def open(self, config: dict) -> None:
          import serial  # lazy import — pyserial

          self._serial = serial.Serial(
              port=config["port"],
              baudrate=int(config.get("baud", 115200)),
              timeout=0.1,
          )

      def close(self) -> None:
          if self._serial is not None:
              self._serial.close()
              self._serial = None

      def read_frames(self) -> Iterator[Frame]:
          assert self._serial is not None
          buf = bytearray()
          in_frame = False
          while True:
              byte = self._serial.read(1)
              if not byte:
                  continue
              b = byte[0]
              if b == STX and not in_frame:
                  in_frame = True
                  buf = bytearray([STX])
                  continue
              if in_frame:
                  buf.append(b)
                  if b == ETX and (len(buf) < 2 or buf[-2] != DLE):
                      in_frame = False
                      frame = parse_frame(bytes(buf))
                      if frame is not None:
                          yield frame

      def write_frame(self, frame: Frame) -> None:
          assert self._serial is not None
          msg = build_n2k_message(prio=3, pgn=frame.pgn, dst=255, src=frame.source_addr, data=frame.data)
          self._serial.write(bytes([STX]) + escape_frame(msg) + bytes([ETX]))


  __all__ = [
      "DLE",
      "ETX",
      "NGT1Driver",
      "STX",
      "build_n2k_message",
      "escape_frame",
      "parse_frame",
      "unescape_frame",
  ]
  ```

- [ ] **Step 12.4: Run, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_actisense_driver.py -q
  ```
  Expected: `4 passed`. If the escape test count differs, recount: `escape_frame` outputs one `DLE` before each of {STX, ETX, DLE} byte. For `[0x10, 0x02, 0x03, 0xAA]` that yields `[0x10, 0x10, 0x10, 0x02, 0x10, 0x03, 0xAA]` — that's 4 `DLE` bytes total. Adjust assertion to `== 4` if the impl produces this.

- [ ] **Step 12.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "drivers/actisense: NGT-1 framing (STX/ETX/DLE), parse, write, read loop"
  ```

---

## Task 13 — Recording (.log writer)

**Create:**
- `/Users/phobic/pgntui/src/pgntui/recording/writer.py`
- `/Users/phobic/pgntui/tests/test_recording_writer.py`

- [ ] **Step 13.1: Write failing test** at `tests/test_recording_writer.py`:
  ```python
  from pathlib import Path

  from pgntui.drivers.base import Frame
  from pgntui.recording.writer import ActisenseLogWriter


  def test_writes_actisense_log_line(tmp_path: Path) -> None:
      path = tmp_path / "rec.pgnlog"
      writer = ActisenseLogWriter(path)
      writer.open()
      writer.write(Frame(timestamp=1717000000.0, source_addr=23, pgn=127488, data=bytes(range(8))))
      writer.close()
      content = path.read_text().strip().split(",")
      assert content[2] == "127488"
      assert content[3] == "23"
      assert content[5] == "8"
      assert content[6:14] == ["00", "01", "02", "03", "04", "05", "06", "07"]
      assert writer.frame_count == 1


  def test_tracks_size_and_count(tmp_path: Path) -> None:
      path = tmp_path / "rec.pgnlog"
      w = ActisenseLogWriter(path)
      w.open()
      for i in range(5):
          w.write(Frame(timestamp=1.0 + i, source_addr=1, pgn=1, data=b"\x00"))
      w.close()
      assert w.frame_count == 5
      assert w.bytes_written > 0
  ```

- [ ] **Step 13.2: Run, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_recording_writer.py -q
  ```

- [ ] **Step 13.3: Implement** `src/pgntui/recording/writer.py`:
  ```python
  """Actisense .log writer."""

  from __future__ import annotations

  from datetime import datetime, timezone
  from pathlib import Path

  from pgntui.drivers.base import Frame


  class ActisenseLogWriter:
      def __init__(self, path: Path) -> None:
          self.path = Path(path)
          self._fh = None
          self.frame_count = 0
          self.bytes_written = 0

      def open(self) -> None:
          self.path.parent.mkdir(parents=True, exist_ok=True)
          self._fh = self.path.open("w", encoding="utf-8")

      def close(self) -> None:
          if self._fh is not None:
              self._fh.close()
              self._fh = None

      def write(self, frame: Frame) -> None:
          assert self._fh is not None
          ts = datetime.fromtimestamp(frame.timestamp, tz=timezone.utc).strftime(
              "%Y-%m-%d-%H:%M:%S.%f"
          )[:-3]
          fields = [
              ts,
              "3",
              str(frame.pgn),
              str(frame.source_addr),
              "255",
              str(len(frame.data)),
              *[f"{b:02x}" for b in frame.data],
          ]
          line = ",".join(fields) + "\n"
          self._fh.write(line)
          self.bytes_written += len(line.encode("utf-8"))
          self.frame_count += 1


  __all__ = ["ActisenseLogWriter"]
  ```

- [ ] **Step 13.4: Run, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_recording_writer.py -q
  ```
  Expected: `2 passed`.

- [ ] **Step 13.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "recording/writer: ActisenseLogWriter with frame-count and size tracking"
  ```

---

## Task 14 — Debug tab

**Create:**
- `/Users/phobic/pgntui/src/pgntui/debug/__init__.py`
- `/Users/phobic/pgntui/src/pgntui/debug/tab.py`
- `/Users/phobic/pgntui/tests/test_debug_tab.py`

- [ ] **Step 14.1: Write failing test** at `tests/test_debug_tab.py`:
  ```python
  from pgntui.debug.tab import DebugBuffer
  from pgntui.decode.canboat import DecodedFrame


  def _df(pgn: int, src: int, name: str = "X") -> DecodedFrame:
      return DecodedFrame(timestamp=1.0, source_addr=src, pgn=pgn, name=name, fields={"a": 1})


  def test_buffer_appends_until_max() -> None:
      buf = DebugBuffer(max_rows=3)
      for i in range(5):
          buf.push(_df(pgn=100 + i, src=1))
      assert len(buf.rows()) == 3
      assert buf.rows()[0].pgn == 102


  def test_pause_blocks_pushes() -> None:
      buf = DebugBuffer(max_rows=10)
      buf.push(_df(127488, 23))
      buf.paused = True
      buf.push(_df(130306, 35))
      assert len(buf.rows()) == 1


  def test_filter_by_pgn() -> None:
      buf = DebugBuffer(max_rows=10, pgn_filter={127488})
      buf.push(_df(127488, 23))
      buf.push(_df(130306, 35))
      assert {r.pgn for r in buf.rows()} == {127488}


  def test_filter_by_source() -> None:
      buf = DebugBuffer(max_rows=10, source_filter={23})
      buf.push(_df(127488, 23))
      buf.push(_df(127488, 99))
      assert all(r.source_addr == 23 for r in buf.rows())


  def test_clear() -> None:
      buf = DebugBuffer(max_rows=10)
      buf.push(_df(1, 1))
      buf.clear()
      assert buf.rows() == []
  ```

- [ ] **Step 14.2: Run, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_debug_tab.py -q
  ```

- [ ] **Step 14.3: Implement** `src/pgntui/debug/__init__.py` empty, then `src/pgntui/debug/tab.py`:
  ```python
  """Debug tab — scrolling decoded-frame buffer with filters."""

  from __future__ import annotations

  from collections import deque

  from pgntui.decode.canboat import DecodedFrame


  class DebugBuffer:
      def __init__(
          self,
          max_rows: int = 1000,
          pgn_filter: set[int] | None = None,
          source_filter: set[int] | None = None,
          show_raw_hex: bool = False,
      ) -> None:
          self._rows: deque[DecodedFrame] = deque(maxlen=max_rows)
          self.paused = False
          self.pgn_filter = pgn_filter
          self.source_filter = source_filter
          self.show_raw_hex = show_raw_hex

      def push(self, df: DecodedFrame) -> None:
          if self.paused:
              return
          if self.pgn_filter is not None and df.pgn not in self.pgn_filter:
              return
          if self.source_filter is not None and df.source_addr not in self.source_filter:
              return
          self._rows.append(df)

      def rows(self) -> list[DecodedFrame]:
          return list(self._rows)

      def clear(self) -> None:
          self._rows.clear()

      def toggle_pause(self) -> None:
          self.paused = not self.paused

      def toggle_raw_hex(self) -> None:
          self.show_raw_hex = not self.show_raw_hex


  __all__ = ["DebugBuffer"]
  ```

- [ ] **Step 14.4: Run, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_debug_tab.py -q
  ```
  Expected: `5 passed`.

- [ ] **Step 14.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "debug/tab: DebugBuffer with pause/filter/clear/raw-hex"
  ```

---

## Task 15 — CSV per-signal logger

**Create:**
- `/Users/phobic/pgntui/src/pgntui/logging/__init__.py`
- `/Users/phobic/pgntui/src/pgntui/logging/csv.py`
- `/Users/phobic/pgntui/tests/test_csv_logger.py`

- [ ] **Step 15.1: Write failing test** at `tests/test_csv_logger.py`:
  ```python
  from datetime import datetime, timezone
  from pathlib import Path

  from pgntui.logging.csv import CSVSignalLogger


  def test_appends_timestamp_value(tmp_path: Path) -> None:
      log = CSVSignalLogger(base_dir=tmp_path)
      log.log("engine_rpm", timestamp=datetime(2026, 6, 4, 12, tzinfo=timezone.utc).timestamp(), value=2150.0)
      log.log("engine_rpm", timestamp=datetime(2026, 6, 4, 12, 0, 1, tzinfo=timezone.utc).timestamp(), value=2160.0)
      log.close()
      f = tmp_path / "engine_rpm-2026-06-04.csv"
      assert f.exists()
      lines = f.read_text().strip().splitlines()
      assert len(lines) == 2
      assert lines[0].endswith("2150.0")


  def test_rotates_at_day_boundary(tmp_path: Path) -> None:
      log = CSVSignalLogger(base_dir=tmp_path)
      day1 = datetime(2026, 6, 4, 23, 59, 59, tzinfo=timezone.utc).timestamp()
      day2 = datetime(2026, 6, 5, 0, 0, 1, tzinfo=timezone.utc).timestamp()
      log.log("x", day1, 1.0)
      log.log("x", day2, 2.0)
      log.close()
      assert (tmp_path / "x-2026-06-04.csv").exists()
      assert (tmp_path / "x-2026-06-05.csv").exists()
  ```

- [ ] **Step 15.2: Run, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_csv_logger.py -q
  ```

- [ ] **Step 15.3: Implement** `src/pgntui/logging/__init__.py` empty, then `src/pgntui/logging/csv.py`:
  ```python
  """Per-signal CSV logger with daily rotation."""

  from __future__ import annotations

  from datetime import datetime, timezone
  from pathlib import Path
  from typing import IO


  class CSVSignalLogger:
      def __init__(self, base_dir: Path) -> None:
          self.base_dir = Path(base_dir)
          self.base_dir.mkdir(parents=True, exist_ok=True)
          self._handles: dict[tuple[str, str], IO[str]] = {}

      def _open(self, signal_id: str, day: str) -> IO[str]:
          key = (signal_id, day)
          fh = self._handles.get(key)
          if fh is None:
              path = self.base_dir / f"{signal_id}-{day}.csv"
              fh = path.open("a", encoding="utf-8")
              self._handles[key] = fh
          return fh

      def log(self, signal_id: str, timestamp: float, value: float | bool) -> None:
          dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
          day = dt.strftime("%Y-%m-%d")
          # close any older-day handles for this signal
          stale = [k for k in self._handles if k[0] == signal_id and k[1] != day]
          for k in stale:
              self._handles.pop(k).close()
          fh = self._open(signal_id, day)
          fh.write(f"{dt.isoformat()},{value}\n")
          fh.flush()

      def close(self) -> None:
          for fh in self._handles.values():
              fh.close()
          self._handles.clear()


  __all__ = ["CSVSignalLogger"]
  ```

- [ ] **Step 15.4: Run, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_csv_logger.py -q
  ```
  Expected: `2 passed`.

- [ ] **Step 15.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "logging/csv: per-signal CSV logger with daily rotation"
  ```

---

## Task 16 — Replay mode UX

**Create:**
- `/Users/phobic/pgntui/src/pgntui/replay_mode.py`
- `/Users/phobic/pgntui/tests/test_replay_mode.py`

- [ ] **Step 16.1: Write failing test** at `tests/test_replay_mode.py`:
  ```python
  from pathlib import Path

  from pgntui.drivers.replay import FileReplayDriver
  from pgntui.replay_mode import ReplaySession, SPEED_LADDER

  FIXTURE = Path(__file__).parent / "fixtures" / "sample.pgnlog"


  def test_speed_cycle() -> None:
      s = ReplaySession(path=FIXTURE)
      start = s.speed
      assert start in SPEED_LADDER
      s.cycle_speed()
      assert s.speed != start


  def test_writes_disabled() -> None:
      s = ReplaySession(path=FIXTURE)
      assert s.write_enabled is False


  def test_iterates_through_file() -> None:
      s = ReplaySession(path=FIXTURE, speed="max")
      driver = s.driver
      assert isinstance(driver, FileReplayDriver)
      s.open()
      frames = list(s.iter_frames())
      s.close()
      assert len(frames) == 3


  def test_pause_resume_state() -> None:
      s = ReplaySession(path=FIXTURE)
      assert not s.paused
      s.toggle_pause()
      assert s.paused
      s.toggle_pause()
      assert not s.paused
  ```

- [ ] **Step 16.2: Run, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_replay_mode.py -q
  ```

- [ ] **Step 16.3: Implement** `src/pgntui/replay_mode.py`:
  ```python
  """Replay session — wraps file-replay driver with transport state."""

  from __future__ import annotations

  from collections.abc import Iterator
  from pathlib import Path

  from pgntui.drivers.base import Frame
  from pgntui.drivers.replay import FileReplayDriver

  SPEED_LADDER = ("0.25x", "0.5x", "1x", "2x", "5x", "10x", "max")


  class ReplaySession:
      write_enabled = False

      def __init__(self, path: Path, speed: str = "1x") -> None:
          self.path = Path(path)
          if speed not in SPEED_LADDER:
              raise ValueError(f"unknown speed {speed!r}")
          self.speed = speed
          self.paused = False
          self.driver = FileReplayDriver()

      def cycle_speed(self) -> None:
          i = SPEED_LADDER.index(self.speed)
          self.speed = SPEED_LADDER[(i + 1) % len(SPEED_LADDER)]

      def toggle_pause(self) -> None:
          self.paused = not self.paused

      def open(self) -> None:
          self.driver.open({"path": str(self.path), "speed": self.speed})

      def close(self) -> None:
          self.driver.close()

      def iter_frames(self) -> Iterator[Frame]:
          yield from self.driver.read_frames()


  __all__ = ["ReplaySession", "SPEED_LADDER"]
  ```

- [ ] **Step 16.4: Run, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_replay_mode.py -q
  ```
  Expected: `4 passed`.

- [ ] **Step 16.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "replay_mode: ReplaySession with speed ladder, pause, write-disabled"
  ```

---

## Task 17 — CLI entry point + config loader

**Create:**
- `/Users/phobic/pgntui/src/pgntui/config.py`
- Modify `/Users/phobic/pgntui/src/pgntui/__main__.py`
- `/Users/phobic/pgntui/tests/test_config.py`
- `/Users/phobic/pgntui/tests/test_cli.py`

- [ ] **Step 17.1: Write failing test** at `tests/test_config.py`:
  ```python
  from pathlib import Path

  from pgntui.config import Config, load_config


  def test_load_config(tmp_path: Path) -> None:
      cfg = tmp_path / "config.toml"
      cfg.write_text(
          '[driver]\nname = "actisense-ngt1"\nport = "/dev/null"\n'
          '[app]\nwrite_enabled = false\ntheme = "dark"\n'
      )
      c = load_config(cfg)
      assert isinstance(c, Config)
      assert c.driver_name == "actisense-ngt1"
      assert c.driver_options["port"] == "/dev/null"
      assert c.theme == "dark"
      assert c.write_enabled is False


  def test_missing_config_returns_defaults(tmp_path: Path) -> None:
      c = load_config(tmp_path / "missing.toml")
      assert c.theme == "dark"
      assert c.write_enabled is False
  ```

  And `tests/test_cli.py`:
  ```python
  from pathlib import Path

  from pgntui.__main__ import parse_args


  def test_parse_no_args() -> None:
      args = parse_args([])
      assert args.command is None
      assert args.workspace is None
      assert args.enable_write is False


  def test_parse_replay_with_file() -> None:
      args = parse_args(["replay", "session.pgnlog"])
      assert args.command == "replay"
      assert args.replay_file == "session.pgnlog"


  def test_parse_workspace_and_enable_write(tmp_path: Path) -> None:
      args = parse_args(["--workspace", str(tmp_path), "--enable-write"])
      assert args.workspace == str(tmp_path)
      assert args.enable_write is True
  ```

- [ ] **Step 17.2: Run, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_config.py tests/test_cli.py -q
  ```

- [ ] **Step 17.3: Implement** `src/pgntui/config.py`:
  ```python
  """TOML config loader."""

  from __future__ import annotations

  import tomllib
  from dataclasses import dataclass, field
  from pathlib import Path


  @dataclass(frozen=True, slots=True)
  class Config:
      driver_name: str = "file-replay"
      driver_options: dict = field(default_factory=dict)
      write_enabled: bool = False
      theme: str = "dark"
      workspace: Path = Path("~/.config/pgntui")
      csv_dir: str = "logs"
      record_dir: str = "recordings"


  def load_config(path: Path) -> Config:
      path = Path(path)
      if not path.exists():
          return Config()
      data = tomllib.loads(path.read_text())
      driver = data.get("driver", {})
      app = data.get("app", {})
      logging_cfg = data.get("logging", {})
      driver_opts = {k: v for k, v in driver.items() if k != "name"}
      return Config(
          driver_name=driver.get("name", "file-replay"),
          driver_options=driver_opts,
          write_enabled=bool(app.get("write_enabled", False)),
          theme=app.get("theme", "dark"),
          workspace=Path(app.get("workspace", "~/.config/pgntui")).expanduser(),
          csv_dir=logging_cfg.get("csv_dir", "logs"),
          record_dir=logging_cfg.get("record_dir", "recordings"),
      )


  __all__ = ["Config", "load_config"]
  ```

  Then update `src/pgntui/__main__.py`:
  ```python
  """CLI entry point for pgntui."""

  from __future__ import annotations

  import argparse
  import sys
  from pathlib import Path

  from pgntui.config import load_config


  def build_parser() -> argparse.ArgumentParser:
      p = argparse.ArgumentParser(prog="pgntui", description="NMEA 2000 terminal UI")
      p.add_argument("--workspace", default=None, help="override workspace directory")
      p.add_argument("--enable-write", action="store_true", help="enable writes")
      sub = p.add_subparsers(dest="command")
      replay = sub.add_parser("replay", help="replay a .pgnlog file")
      replay.add_argument("replay_file")
      return p


  def parse_args(argv: list[str]) -> argparse.Namespace:
      return build_parser().parse_args(argv)


  def main(argv: list[str] | None = None) -> int:
      args = parse_args(argv if argv is not None else sys.argv[1:])
      workspace = Path(args.workspace).expanduser() if args.workspace else Path("~/.config/pgntui").expanduser()
      cfg_path = workspace / "config.toml"
      cfg = load_config(cfg_path)
      if args.enable_write:
          # Re-create with write_enabled flipped on
          cfg = type(cfg)(
              driver_name=cfg.driver_name,
              driver_options=cfg.driver_options,
              write_enabled=True,
              theme=cfg.theme,
              workspace=workspace,
              csv_dir=cfg.csv_dir,
              record_dir=cfg.record_dir,
          )
      if args.command == "replay":
          # Replay mode is bootstrapped here in a later integration step.
          print(f"replay: {args.replay_file} (workspace={workspace}, theme={cfg.theme})")
          return 0
      print(f"pgntui: workspace={workspace} theme={cfg.theme} write_enabled={cfg.write_enabled}")
      return 0


  if __name__ == "__main__":
      raise SystemExit(main())
  ```

- [ ] **Step 17.4: Run, confirm pass.** Smoke tests must still pass.
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_config.py tests/test_cli.py tests/test_smoke.py -q
  ```
  Expected: `5 passed` plus the original smoke tests passing.

- [ ] **Step 17.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "config + cli: TOML loader, argparse with replay/workspace/enable-write"
  ```

---

## Task 18 — Built-in themes

**Create / Modify:**
- `/Users/phobic/pgntui/src/pgntui/themes/builtin/dark.json` (already exists — keep)
- `/Users/phobic/pgntui/src/pgntui/themes/builtin/light.json`
- `/Users/phobic/pgntui/src/pgntui/themes/builtin/amber-crt.json`
- `/Users/phobic/pgntui/src/pgntui/themes/builtin/green-phosphor.json`
- `/Users/phobic/pgntui/src/pgntui/themes/builtin/mono-ascii.json`
- `/Users/phobic/pgntui/src/pgntui/themes/builtin/rainbow-disco.json`
- `/Users/phobic/pgntui/tests/test_builtin_themes.py`

- [ ] **Step 18.1: Write failing test** at `tests/test_builtin_themes.py`:
  ```python
  import pytest

  from pgntui.themes.loader import load_builtin, to_textual_css

  BUILTINS = ["dark", "light", "amber-crt", "green-phosphor", "mono-ascii", "rainbow-disco"]


  @pytest.mark.parametrize("name", BUILTINS)
  def test_each_builtin_loads(name: str) -> None:
      theme = load_builtin(name)
      assert theme.id == name


  @pytest.mark.parametrize("name", BUILTINS)
  def test_each_builtin_renders_css(name: str) -> None:
      theme = load_builtin(name)
      css = to_textual_css(theme)
      assert "Screen {" in css
      assert ".bar-fill" in css


  def test_rainbow_has_gradient_and_animate() -> None:
      theme = load_builtin("rainbow-disco")
      assert theme.gradients
      assert theme.animate is True


  def test_mono_ascii_uses_ascii_glyphs() -> None:
      theme = load_builtin("mono-ascii")
      assert theme.glyphs["box"] == "ascii"
  ```

- [ ] **Step 18.2: Run, confirm failure** (only `dark` exists).
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_builtin_themes.py -q
  ```

- [ ] **Step 18.3: Write each theme JSON.**

  `light.json`:
  ```json
  {
    "id": "light", "title": "Light",
    "colors": {
      "bg": "#f5f5f5", "fg": "#202020", "fg_dim": "#808080",
      "accent": "#0a66c2", "ok": "#1f7a1f", "warn": "#a06400", "alarm": "#a01a1a",
      "border": "#c0c0c0", "title_bg": "#e0e0e0", "title_fg": "#202020",
      "bar_track": "#d0d0d0", "bar_fill": "#0a66c2",
      "bar_warn": "#a06400", "bar_alarm": "#a01a1a"
    },
    "glyphs": {"bar_left": "├", "bar_right": "┤", "bar_track": "─",
               "bar_marker": "●", "on": "●", "off": "○", "box": "single"},
    "styles": {"title": "bold", "value": "bold", "unit": "dim"}
  }
  ```

  `amber-crt.json`:
  ```json
  {
    "id": "amber-crt", "title": "Amber CRT",
    "colors": {
      "bg": "#1a0f00", "fg": "#ffb000", "fg_dim": "#7a5400",
      "accent": "#ffe07a", "ok": "#5cff5c", "warn": "#ffcc33", "alarm": "#ff3030",
      "border": "#7a5400", "title_bg": "#3a2200", "title_fg": "#ffe07a",
      "bar_track": "#3a2200", "bar_fill": "#ffb000",
      "bar_warn": "#ffcc33", "bar_alarm": "#ff3030"
    },
    "glyphs": {"bar_left": "├", "bar_right": "┤", "bar_track": "─",
               "bar_marker": "●", "on": "●", "off": "○", "box": "single"},
    "styles": {"title": "bold", "value": "bold", "unit": "dim"}
  }
  ```

  `green-phosphor.json`:
  ```json
  {
    "id": "green-phosphor", "title": "Green Phosphor",
    "colors": {
      "bg": "#001a00", "fg": "#33ff33", "fg_dim": "#1a7a1a",
      "accent": "#a0ffa0", "ok": "#33ff33", "warn": "#ffff33", "alarm": "#ff5050",
      "border": "#1a7a1a", "title_bg": "#003300", "title_fg": "#a0ffa0",
      "bar_track": "#003300", "bar_fill": "#33ff33",
      "bar_warn": "#ffff33", "bar_alarm": "#ff5050"
    },
    "glyphs": {"bar_left": "├", "bar_right": "┤", "bar_track": "─",
               "bar_marker": "●", "on": "●", "off": "○", "box": "single"},
    "styles": {"title": "bold", "value": "bold", "unit": "dim"}
  }
  ```

  `mono-ascii.json`:
  ```json
  {
    "id": "mono-ascii", "title": "Mono ASCII",
    "colors": {
      "bg": "#000000", "fg": "#ffffff", "fg_dim": "#808080",
      "accent": "#ffffff", "ok": "#ffffff", "warn": "#ffffff", "alarm": "#ffffff",
      "border": "#808080", "title_bg": "#000000", "title_fg": "#ffffff",
      "bar_track": "#404040", "bar_fill": "#ffffff",
      "bar_warn": "#ffffff", "bar_alarm": "#ffffff"
    },
    "glyphs": {"bar_left": "|", "bar_right": "|", "bar_track": "-",
               "bar_marker": "*", "on": "*", "off": "o", "box": "ascii"},
    "styles": {"title": "bold", "value": "", "unit": ""}
  }
  ```

  `rainbow-disco.json`:
  ```json
  {
    "id": "rainbow-disco", "title": "Rainbow Disco",
    "colors": {
      "bg": "#0a0014", "fg": "#ffffff", "fg_dim": "#9070a0",
      "accent": "#ff00ff", "ok": "#00ff80", "warn": "#ffd000", "alarm": "#ff0040",
      "border": "#ff00ff", "title_bg": "#1a0028", "title_fg": "#ffd0ff",
      "bar_track": "#1a0028", "bar_fill": "#ff00ff",
      "bar_warn": "#ffd000", "bar_alarm": "#ff0040"
    },
    "glyphs": {"bar_left": "├", "bar_right": "┤", "bar_track": "─",
               "bar_marker": "●", "on": "●", "off": "○", "box": "double"},
    "styles": {"title": "bold", "value": "bold", "unit": "dim"},
    "gradients": [
      {"target": "bar_fill",  "stops": ["#ff0000","#ff8000","#ffff00","#00ff00","#00ffff","#0080ff","#8000ff","#ff00ff"]},
      {"target": "title_fg",  "stops": ["#ff80ff","#ffd080","#80ff80","#80ffff","#8080ff","#ff80c0"]},
      {"target": "border",    "stops": ["#ff00ff","#00ffff","#ffff00","#ff8000"]}
    ],
    "animate": true,
    "animate_fps": 4
  }
  ```

- [ ] **Step 18.4: Run, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest tests/test_builtin_themes.py -q
  ```
  Expected: `14 passed` (6 load + 6 css + 2 specific).

- [ ] **Step 18.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "themes/builtin: light, amber-crt, green-phosphor, mono-ascii, rainbow-disco"
  ```

---

## Task 19 — End-to-end replay test

**Create:**
- `/Users/phobic/pgntui/tests/fixtures/e2e_session.pgnlog`
- `/Users/phobic/pgntui/tests/fixtures/e2e_signals/engine_rpm.json`
- `/Users/phobic/pgntui/tests/fixtures/e2e_signals/wind_speed.json`
- `/Users/phobic/pgntui/tests/fixtures/e2e_containers/engine.json`
- `/Users/phobic/pgntui/tests/fixtures/e2e_containers/nav.json`
- `/Users/phobic/pgntui/tests/test_e2e_replay.py`

- [ ] **Step 19.1: Write fixture session** at `tests/fixtures/e2e_session.pgnlog` (PGN 127488 engine speed = 2150 rpm at byte offset 1, PGN 130306 wind speed):
  ```
  2026-06-04-15:42:01.000,2,127488,23,255,8,00,98,21,0c,00,00,ff,ff
  2026-06-04-15:42:01.500,2,127488,23,255,8,00,98,21,0c,00,00,ff,ff
  2026-06-04-15:42:02.000,2,130306,35,255,8,00,fa,00,b4,00,00,fa,ff
  2026-06-04-15:42:02.500,2,127488,23,255,8,00,98,21,0c,00,00,ff,ff
  ```

- [ ] **Step 19.2: Write fixture signals/containers.**

  `tests/fixtures/e2e_signals/engine_rpm.json`:
  ```json
  {"id": "engine_rpm", "type": "analog_in", "title": "Engine RPM",
   "unit": "rpm", "pgn": 127488, "field": "Engine Speed",
   "source": 23, "min": 0, "max": 6000, "decimals": 0, "log": true}
  ```

  `tests/fixtures/e2e_signals/wind_speed.json`:
  ```json
  {"id": "wind_speed", "type": "analog_in", "title": "Wind Speed",
   "unit": "kn", "pgn": 130306, "field": "Wind Speed",
   "source": 35, "min": 0, "max": 60, "decimals": 1}
  ```

  `tests/fixtures/e2e_containers/engine.json`:
  ```json
  {"id": "engine", "title": "Engine", "cols": 12,
   "signals": [{"ref": "engine_rpm", "row": 0, "col": 0, "w": 12}]}
  ```

  `tests/fixtures/e2e_containers/nav.json`:
  ```json
  {"id": "nav", "title": "Nav", "cols": 12,
   "signals": [{"ref": "wind_speed", "row": 0, "col": 0, "w": 12}]}
  ```

- [ ] **Step 19.3: Write failing test** at `tests/test_e2e_replay.py`:
  ```python
  from pathlib import Path

  from pgntui.containers.loader import load_container
  from pgntui.decode.canboat import CanboatDecoder
  from pgntui.decode.router import SignalKey, SignalRouter
  from pgntui.drivers.replay import FileReplayDriver
  from pgntui.logging.csv import CSVSignalLogger
  from pgntui.signals.base import AnalogIn, load_signals_dir

  FX = Path(__file__).parent / "fixtures"


  def test_e2e_replay_drives_signals_and_csv(tmp_path: Path) -> None:
      signals = {s.id: s for s in load_signals_dir(FX / "e2e_signals")}
      assert set(signals) == {"engine_rpm", "wind_speed"}
      containers = [
          load_container(FX / "e2e_containers" / "engine.json", set(signals)),
          load_container(FX / "e2e_containers" / "nav.json", set(signals)),
      ]
      assert {c.id for c in containers} == {"engine", "nav"}

      decoder = CanboatDecoder.load_bundled()
      router = SignalRouter()
      for sid, sig in signals.items():
          router.bind(sid, SignalKey(pgn=sig.pgn, field=sig.field, source=sig.source))

      driver = FileReplayDriver()
      driver.open({"path": str(FX / "e2e_session.pgnlog"), "speed": "max"})

      csv_logger = CSVSignalLogger(base_dir=tmp_path)
      last: dict[str, float] = {}

      for frame in driver.read_frames():
          decoded = decoder.decode(frame)
          if decoded is None:
              continue
          for update in router.route(decoded):
              last[update.signal_id] = float(update.value)
              sig = signals[update.signal_id]
              if sig.log and isinstance(sig, AnalogIn):
                  csv_logger.log(update.signal_id, update.timestamp, float(update.value))

      driver.close()
      csv_logger.close()

      assert "engine_rpm" in last
      assert 2140 <= last["engine_rpm"] <= 2160
      assert "wind_speed" in last

      logs = list(tmp_path.glob("engine_rpm-*.csv"))
      assert logs, "expected engine_rpm CSV"
      assert len(logs[0].read_text().strip().splitlines()) == 3
  ```

- [ ] **Step 19.4: Run, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_e2e_replay.py -q
  ```
  Expected: `1 passed`. If the wind-speed assertion fails because canboat names the field differently (e.g. `"Wind Speed"` vs `"Speed"`), open `src/pgntui/decode/pgns.json` and search for `130306` to confirm the exact field name, then update `wind_speed.json` and the test accordingly.

- [ ] **Step 19.5: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "test: end-to-end replay drives signal updates and CSV"
  ```

---

## Task 20 — Packaging + release

**Create / Modify:**
- Modify `/Users/phobic/pgntui/pyproject.toml`
- `/Users/phobic/pgntui/.github/workflows/release.yml`
- `/Users/phobic/pgntui/pgntui.spec`
- `/Users/phobic/pgntui/packaging/homebrew/pgntui.rb`
- `/Users/phobic/pgntui/packaging/winget/phobic.pgntui.yaml`
- `/Users/phobic/pgntui/tests/test_packaging.py`

- [ ] **Step 20.1: Write failing test** at `tests/test_packaging.py`:
  ```python
  from pathlib import Path

  ROOT = Path(__file__).resolve().parent.parent


  def test_pyproject_has_full_classifiers() -> None:
      text = (ROOT / "pyproject.toml").read_text()
      for cls in (
          "License :: OSI Approved :: MIT License",
          "Programming Language :: Python :: 3.11",
          "Programming Language :: Python :: 3.12",
          "Programming Language :: Python :: 3.13",
          "Operating System :: MacOS",
          "Operating System :: POSIX :: Linux",
          "Operating System :: Microsoft :: Windows",
          "Topic :: Terminals",
      ):
          assert cls in text


  def test_release_workflow_exists_and_targets_pypi() -> None:
      wf = (ROOT / ".github/workflows/release.yml").read_text()
      assert "pypa/gh-action-pypi-publish" in wf
      assert "phobicdotno/pgntui" in wf or "${{ github.repository }}" in wf


  def test_pyinstaller_spec_exists() -> None:
      assert (ROOT / "pgntui.spec").exists()


  def test_homebrew_tap_stub_exists() -> None:
      tap = (ROOT / "packaging/homebrew/pgntui.rb").read_text()
      assert "class Pgntui" in tap
      assert "phobicdotno/homebrew-tap" in tap


  def test_winget_manifest_stub_exists() -> None:
      manifest = (ROOT / "packaging/winget/phobic.pgntui.yaml").read_text()
      assert "PackageIdentifier: phobic.pgntui" in manifest
  ```

- [ ] **Step 20.2: Run, confirm failure.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_packaging.py -q
  ```

- [ ] **Step 20.3: Write release workflow** at `.github/workflows/release.yml`:
  ```yaml
  name: release
  on:
    push:
      tags: ["v*"]

  jobs:
    pypi:
      runs-on: ubuntu-latest
      permissions:
        id-token: write
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: "3.12" }
        - run: pip install build
        - run: python -m build
        - name: Publish to PyPI (Trusted Publisher)
          uses: pypa/gh-action-pypi-publish@release/v1

    binaries:
      strategy:
        fail-fast: false
        matrix:
          include:
            - os: macos-14
              arch: arm64
              asset: pgntui-macos-arm64
            - os: macos-13
              arch: x86_64
              asset: pgntui-macos-x86_64
            - os: ubuntu-latest
              arch: x86_64
              asset: pgntui-linux-x86_64
            - os: windows-latest
              arch: x86_64
              asset: pgntui-windows-x86_64.exe
      runs-on: ${{ matrix.os }}
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: "3.12" }
        - run: pip install -e ".[dev]"
        - run: pyinstaller pgntui.spec
        - name: Upload binary
          uses: softprops/action-gh-release@v2
          with:
            files: dist/${{ matrix.asset }}

    homebrew_winget:
      needs: [pypi, binaries]
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - name: Update homebrew tap stub (manual follow-up to phobicdotno/homebrew-tap)
          run: echo "Bump packaging/homebrew/pgntui.rb in phobicdotno/homebrew-tap for ${GITHUB_REF_NAME}"
        - name: Update winget manifest stub (manual follow-up to microsoft/winget-pkgs)
          run: echo "Bump packaging/winget/phobic.pgntui.yaml PR to microsoft/winget-pkgs for ${GITHUB_REF_NAME}"
  ```

- [ ] **Step 20.4: Write PyInstaller spec** at `pgntui.spec`:
  ```python
  # -*- mode: python ; coding: utf-8 -*-
  block_cipher = None

  a = Analysis(
      ["src/pgntui/__main__.py"],
      pathex=["src"],
      binaries=[],
      datas=[
          ("src/pgntui/decode/pgns.json", "pgntui/decode"),
          ("src/pgntui/themes/builtin", "pgntui/themes/builtin"),
      ],
      hiddenimports=["pgntui.drivers.actisense", "pgntui.drivers.replay"],
      hookspath=[],
      hooksconfig={},
      runtime_hooks=[],
      excludes=[],
      win_no_prefer_redirects=False,
      win_private_assemblies=False,
      cipher=block_cipher,
      noarchive=False,
  )
  pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
  exe = EXE(
      pyz,
      a.scripts,
      a.binaries,
      a.zipfiles,
      a.datas,
      [],
      name="pgntui",
      debug=False,
      bootloader_ignore_signals=False,
      strip=False,
      upx=False,
      runtime_tmpdir=None,
      console=True,
      disable_windowed_traceback=False,
      target_arch=None,
      codesign_identity=None,
      entitlements_file=None,
  )
  ```

- [ ] **Step 20.5: Write Homebrew tap stub** at `packaging/homebrew/pgntui.rb`:
  ```ruby
  # Stub formula for phobicdotno/homebrew-tap
  # Install: brew install phobicdotno/tap/pgntui
  class Pgntui < Formula
    desc "Cross-platform TUI for NMEA 2000 with canboat decoding"
    homepage "https://github.com/phobicdotno/pgntui"
    url "https://files.pythonhosted.org/packages/source/p/pgntui/pgntui-0.1.0.tar.gz"
    sha256 "REPLACE_ON_RELEASE"
    license "MIT"

    depends_on "python@3.12"

    def install
      virtualenv_install_with_resources
    end

    test do
      assert_match "pgntui", shell_output("#{bin}/pgntui --help", 2)
    end
  end
  ```

- [ ] **Step 20.6: Write WinGet manifest stub** at `packaging/winget/phobic.pgntui.yaml`:
  ```yaml
  # Stub manifest for microsoft/winget-pkgs PR
  PackageIdentifier: phobic.pgntui
  PackageVersion: 0.1.0
  PackageLocale: en-US
  Publisher: phobic
  PackageName: pgntui
  License: MIT
  ShortDescription: Cross-platform TUI for NMEA 2000
  Description: |
    Terminal UI for NMEA 2000 networks. Reads via pluggable drivers
    (Actisense NGT-1, file replay), decodes via canboat pgns.json,
    renders JSON-configured dashboards.
  Moniker: pgntui
  Tags: [nmea, marine, tui, terminal]
  Installers:
    - Architecture: x64
      InstallerType: portable
      InstallerUrl: https://github.com/phobicdotno/pgntui/releases/download/v0.1.0/pgntui-windows-x86_64.exe
      InstallerSha256: REPLACE_ON_RELEASE
  ManifestType: singleton
  ManifestVersion: 1.6.0
  ```

- [ ] **Step 20.7: Confirm `pyproject.toml` already carries all required classifiers** (set in Task 1). If `Topic :: Terminals` is missing, add it now.

- [ ] **Step 20.8: Run packaging test, confirm pass.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/pytest tests/test_packaging.py -q
  ```
  Expected: `5 passed`.

- [ ] **Step 20.9: Run full suite as final check.**
  ```bash
  cd /Users/phobic/pgntui && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy src/pgntui && .venv/bin/pytest -q
  ```
  All must pass. Fix any lint/format/type errors inline before commit.

- [ ] **Step 20.10: Commit.**
  ```bash
  cd /Users/phobic/pgntui && git add -A && git commit -m "release: GitHub Actions PyPI trusted publisher, PyInstaller spec, Homebrew + WinGet stubs"
  ```

---

## Done

After Task 20, you have:
- A passing test suite covering decode, router, signals, containers, themes, widgets, drivers (live + replay), recording, CSV logging, replay UX, CLI, and packaging artifacts.
- Bundled `pgns.json`, 6 built-in themes including `rainbow-disco`.
- Actisense NGT-1 driver wired via entry point, file-replay driver wired via entry point.
- CI matrix for macOS / Linux / Windows on Python 3.11/3.12/3.13.
- Tag-triggered PyPI publish via Trusted Publisher binding (account `phobic`, repo `phobicdotno/pgntui`), PyInstaller binaries attached to GitHub Releases, and Homebrew + WinGet stubs ready to copy into their respective tap/manifest repos.
