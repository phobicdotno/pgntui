# Audit C: Cross-Platform + Encoding + Types + Schema (2026-06-04)
Branch: main @ 1f3795d (v0.2.1)
Auditor: feature-dev:code-reviewer

## Findings

### C-1: Default workspace `~/.config/pgntui` non-standard on Windows
- **Files:** `src/pgntui/__main__.py:23`; `src/pgntui/config.py:17,36`; `src/pgntui/app.py:329`
- **Severity:** Important
- **What's wrong:** `~/.config/pgntui` is Linux convention. Windows: `%APPDATA%/pgntui`. macOS: `~/Library/Application Support/pgntui`. `platformdirs.user_config_dir("pgntui")` returns correct per-OS path.
- **Fix:** Use `platformdirs`. Add to dependencies.

### C-2: Threshold fields not coerced to float in signal loader
- **File:** `src/pgntui/signals/base.py:101-104, 116-119`
- **Severity:** Important
- **What's wrong:** `warn_above`/`alarm_above`/`warn_below`/`alarm_below` typed `float | None` but loader passes `payload.get(...)` raw — JSON `5000` parses as `int`. mypy strict violation; downstream comparisons work at runtime but type contract is broken.
- **Fix:** Wrap each with `float(payload[k]) if k in payload else None`.

### C-3: PyInstaller spec omits `pgntui.examples` — `--example` crashes in binary
- **File:** `pgntui.spec:6-9`
- **Severity:** Critical
- **What's wrong:** `scaffold_example()` uses `resources.files("pgntui.examples")`. Spec doesn't include `examples/` in `datas`. Frozen binary raises `FileNotFoundError`.
- **Fix:** Add `("src/pgntui/examples", "pgntui/examples")` to datas + `pgntui.examples` to hiddenimports. **DUPLICATE of D-C1.**

### C-4: ActisenseLogWriter text mode → CRLF on Windows
- **File:** `src/pgntui/recording/writer.py:21`
- **Severity:** Important
- **What's wrong:** `path.open("w", encoding="utf-8")` — on Windows `\n` → `\r\n`. `bytes_written` understates file size. Replay tolerates via `strip()` but downstream binary tools see CRLF pollution.
- **Fix:** `self._fh = self.path.open("w", encoding="utf-8", newline="")`.

### C-5: TOML syntax errors produce raw Python traceback
- **File:** `src/pgntui/config.py:26`
- **Severity:** Important
- **What's wrong:** `tomllib.loads(...)` not wrapped. `TOMLDecodeError` propagates to user as stack trace instead of "config.toml line 5: invalid TOML".
- **Fix:** Wrap with `try/except tomllib.TOMLDecodeError` raising `ValueError`; catch in `main()` print + exit 1.

### C-6: `textual>=0.80` lower bound far too loose
- **File:** `pyproject.toml:27`
- **Severity:** Important
- **What's wrong:** Code targets Textual 8.x API (`@work(thread=True)`, `RichLog`, kw-only `read_from`). `textual==0.80.x` is a different major; user pip-installing could resolve to 0.80.x. APIs may not exist.
- **Fix:** Bump to `textual>=8.0`.

### C-7: `_views` property type hole via `__dict__.setdefault`
- **File:** `src/pgntui/app.py:156`
- **Severity:** Important
- **What's wrong:** `self.__dict__.setdefault("_view_pairs", [])` + `# type: ignore[no-any-return]`. mypy can't verify the actual list type.
- **Fix:** Declare `self._view_pairs: list[tuple[Container, ContainerView]] = []` in `__init__`, remove property, reference directly.

### C-8: Float formatting locale risk (low)
- **File:** `src/pgntui/signals/widgets.py:45,85`
- **Severity:** Low (CPython f-strings are locale-neutral; theoretical risk only)
- **Fix:** No action needed; document if certainty matters.

## Clean
- All JSON loaders use `encoding="utf-8"` explicitly
- CSV logger UTF-8
- TOML reader UTF-8
- Recording reader UTF-8
- All bundled-data access via `importlib.resources` (no `__file__` paths)
- `scaffold_example` uses `resources.files(...).iterdir()` correctly
- `datetime.now(tz=UTC)` consistently used
- No Python 3.12+ syntax
- All `type: ignore` narrow + documented except C-7
- All Signal/Frame/Theme dataclasses are `frozen=True`; no `object.__setattr__` mutation
- Loaders raise typed exceptions on missing required keys
- Numeric fields (pgn, cols, row, col, w, min, max, decimals, smoothing) all pass through int()/float() coercion
- No hardcoded `/` separators in JSON
- `serial` import deferred inside `open()` with single narrow type ignore

## Notes
- C-3 only manifests in binary builds; `test_packaging.py` only checks .spec existence
- C-6 cannot be fully resolved without testing against textual 0.80.x; safest to bump
- `load_config` returns default Config for missing TOML file (intentional, clean)
- `_copy_resource_tree` `iterdir()` type ignore is a known mypy/resources API gap
