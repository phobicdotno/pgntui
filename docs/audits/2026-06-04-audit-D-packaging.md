# Audit D: Packaging + Distribution + Test Gaps (2026-06-04)
Branch: main @ 1f3795d (v0.2.1)
Auditor: feature-dev:code-reviewer

## CRITICAL

### C1: PyInstaller spec missing `examples/` in `datas` — frozen binary can't scaffold
- **File:** `pgntui.spec:6-9`
- **What's wrong:** Spec bundles `decode/pgns.json` and `themes/builtin/` but not `examples/`. The `--example` flag uses `resources.files("pgntui.examples")` at runtime; PyInstaller resolves via `sys._MEIPASS` only if listed in `datas`. Without it the traversal finds nothing.
- **Fix:** Add `("src/pgntui/examples", "pgntui/examples")` to `datas`.

### C2: Frozen binary: `entry_points` lookup returns empty — NGT-1 driver never loads
- **File:** `pgntui.spec:10`, `src/pgntui/__main__.py:132-149`
- **What's wrong:** `load_driver()` calls `importlib.metadata.entry_points(group="pgntui.drivers")`. PyInstaller needs `METADATA`/`entry_points.txt` bundled via `copy_metadata("pgntui")` in `datas`, or a hook. Neither present. Result: `load_driver("actisense-ngt1")` returns `None` in the binary; NGT-1 silently dead.
- **Fix:** `from PyInstaller.utils.hooks import copy_metadata` + `datas=[..., *copy_metadata("pgntui")]`. Alternatively hard-wire driver registry in `__main__.py` for frozen path.

## IMPORTANT

### I1: `release.yml` jobs have no `timeout-minutes`
- **File:** `.github/workflows/release.yml:23-52`
- **What's wrong:** Default 6-hour timeout. macOS-13 PyInstaller routinely 20-40min; hangs block `homebrew_winget` silently.
- **Fix:** `timeout-minutes: 30` on binaries job, `10` on pypi.

### I2: PyPI publish has no CI gate — can ship broken code
- **File:** `.github/workflows/release.yml:9-21`
- **What's wrong:** Tag triggers publish independently of CI passing.
- **Fix:** Add reusable-workflow `needs: ci` at top of `release.yml`, OR enforce CI as required status check on tag branch protection.

### I3: `pyproject.toml` missing `[project.urls]`
- **What's wrong:** PyPI sidebar is empty (no Homepage, Source, Issues). Looks unmaintained.
- **Fix:**
  ```toml
  [project.urls]
  Homepage = "https://github.com/phobicdotno/pgntui"
  Source = "https://github.com/phobicdotno/pgntui"
  "Bug Tracker" = "https://github.com/phobicdotno/pgntui/issues"
  ```

### I4: README is 16 lines, no screenshots/feature list/config example
- **File:** `README.md`
- **What's wrong:** This is the PyPI long description. Spec link is repo-relative, dead on PyPI.
- **Fix:** Expand: install, ASCII demo, workspace config format, driver list, replay usage. Remove or make absolute the internal spec link.

### I5: homebrew/winget stubs have `REPLACE_ON_RELEASE` placeholders — never auto-filled
- **Files:** `packaging/homebrew/pgntui.rb:7`, `packaging/winget/phobic.pgntui.yaml:18`
- **What's wrong:** `release.yml`'s `homebrew_winget` job is an `echo` stub. Human follow-up will publish invalid manifests if they copy-paste.
- **Fix:** Add `packaging/README.md` documenting manual steps, OR a release-checklist test asserting `REPLACE_ON_RELEASE` is absent from any released artifact.

### I6: `test_iter_frames_honors_pause_with_sliding_resume` flakiness risk on loaded CI
- **File:** `tests/test_replay_mode.py:59-118`
- **What's wrong:** 25ms threshold = exactly one poll quantum (50ms) - jitter. `time.sleep(0.6)` post-pause vs 200ms inter-frame: under high scheduler latency, frame 2 could emit before pause lands.
- **Fix:** Increase `spacing_ms` to 500ms, observation window to 1.5s, document the timing floor in a comment.

### I7: Minor — `test_packaging.py` failure mode
- **File:** `tests/test_packaging.py:33-39`
- **What's wrong:** If `packaging/` is ever moved, read raises `FileNotFoundError` rather than `AssertionError`, confusing traceback.
- **Fix:** Wrap reads in explicit existence asserts first.

## Clean
- All 6 `themes/builtin/*.json` listed in pyproject.force-include match files on disk
- `decode/pgns.json` present in both pyproject AND pgntui.spec
- `examples/` files all in pyproject.force-include — wheel coverage complete
- No `[tool.hatch.build.targets.sdist]` customization — hatchling defaults include full `src/` tree
- `.gitignore` excludes `__pycache__` from wheel/sdist
- CI matrix: ubuntu-latest, macos-latest, windows-latest × Python 3.11/3.12/3.13
- ruff check, ruff format --check, mypy enforced as hard gates
- pytest `asyncio_mode = "auto"` — no per-test opt-in
- PyInstaller `console=True`, `runtime_tmpdir=None` correct for TUI binary
- `softprops/action-gh-release@v2` correctly attaches all 4 matrix artifacts to one release
- `NGT1Driver` parse logic exercised via mock serial (no hardware required)
- All `src/pgntui/` modules have corresponding test files
- `homebrew_winget` job clearly documented as manual stub via `echo`
- PyPI Trusted Publisher comment correctly names `release.yml`

## Notes
- `.gitignore` contains `*.spec`, overridden by tracking. Future `git add .` after regenerating spec could silently fail to stage. Consider removing `*.spec` from `.gitignore`.
- Default `driver_name = "file-replay"` in fresh `Config` → `FileReplayDriver.open({})` raises KeyError (no path) → swallowed by `open_driver_or_none` → app starts in no-driver mode. Correct UX, confusing logs. No test covers default-command-path with no workspace.
