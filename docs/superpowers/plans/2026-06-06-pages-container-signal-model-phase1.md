# Page → Container → Signal model — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat container/group schema with an enforced Page → Container → Signal model so every signal lives inside a titled container box, fixing the orphaned-signal (Engine) and box-less (Main) layouts.

**Architecture:** Additive-then-flip rename. First add the new loader model (`Page`/`Container`), a migrator, and the new `PageView` renderer alongside the existing code (suite stays green). Then flip `app.py`/`__main__.py` and the example workspace to the new model, update tests, and delete the dead old symbols. New nested JSON schema only — no runtime back-compat; a `--migrate-workspace` CLI converts old workspaces once.

**Tech Stack:** Python 3.11, Textual 8.2, pytest + pytest-asyncio, hatch build, ruff, mypy. Run tools via `.venv/Scripts/python.exe -m <tool>`.

**Spec:** `docs/superpowers/specs/2026-06-06-pages-container-signal-model-design.md`

---

## File Structure

- `src/pgntui/containers/loader.py` — **modify**: add `Page`, redefine `Container`, container-relative `SignalPlacement`, `InstanceOption`, `load_page`, `PageLoadError`. (Old `Container`/`GroupHeader`/`load_container`/`ContainerLoadError` removed in Task 7.)
- `src/pgntui/containers/migrate.py` — **create**: pure old→new dict conversion (`migrate_page_dict`) + file/dir helpers (`migrate_workspace`).
- `src/pgntui/containers/screen.py` — **modify**: add `PageView` (renders a `Page`'s containers as `GroupBox` boxes); keep `GroupBox`, `GroupRule`. Remove `ContainerView`/`ContainerScreen` in Task 7.
- `src/pgntui/app.py` — **modify**: `compose()` builds one `TabPane` per Page; `_page_views`; page-level instance actions; constructor takes `pages`/`page_titles`.
- `src/pgntui/__main__.py` — **modify**: `discover_pages`, `_build_app` passes `pages=`, `--migrate-workspace` flag.
- `src/pgntui/examples/containers/*.json` — **modify**: rewritten to new schema.
- Tests: **create** `tests/test_pages_loader.py`, `tests/test_migrate_workspace.py`; **modify** `tests/test_container_groups.py`, `tests/test_instance_switch.py`, `tests/test_app_container_visible.py`, `tests/test_main_replay.py`, `tests/test_app_empty_welcome.py`.

Run the full suite with `.venv/Scripts/python.exe -m pytest -q` and lint with `.venv/Scripts/python.exe -m ruff check src tests` + `.venv/Scripts/python.exe -m mypy src/pgntui`.

---

## Task 1: New loader model + `load_page`

**Files:**
- Modify: `src/pgntui/containers/loader.py`
- Test: `tests/test_pages_loader.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pages_loader.py
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from pgntui.containers.loader import (
    Container,
    Page,
    PageLoadError,
    SignalPlacement,
    load_page,
)


def _load(payload: dict, ids: set[str]) -> Page:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "p.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        return load_page(p, ids)


def test_parses_nested_page() -> None:
    page = _load(
        {
            "id": "engine",
            "title": "Engine",
            "instances": [{"id": 0, "label": "Stb"}],
            "containers": [
                {
                    "title": "Drive",
                    "cols": 12,
                    "signals": [
                        {"ref": "rpm", "row": 0, "col": 0, "w": 12},
                        {"ref": "boost", "row": 1, "col": 0, "w": 6},
                    ],
                }
            ],
        },
        {"rpm", "boost"},
    )
    assert page.id == "engine"
    assert page.instances[0].label == "Stb"
    assert len(page.containers) == 1
    c = page.containers[0]
    assert isinstance(c, Container)
    assert c.title == "Drive" and c.cols == 12
    assert c.signals[0] == SignalPlacement(ref="rpm", row=0, col=0, w=12)


def test_rejects_unknown_ref() -> None:
    with pytest.raises(PageLoadError):
        _load(
            {"id": "p", "title": "P", "containers": [
                {"title": "C", "cols": 12, "signals": [{"ref": "nope", "row": 0, "col": 0, "w": 6}]}
            ]},
            set(),
        )


def test_rejects_overlap_within_container() -> None:
    with pytest.raises(PageLoadError):
        _load(
            {"id": "p", "title": "P", "containers": [
                {"title": "C", "cols": 12, "signals": [
                    {"ref": "a", "row": 0, "col": 0, "w": 6},
                    {"ref": "b", "row": 0, "col": 3, "w": 6},
                ]}
            ]},
            {"a", "b"},
        )


def test_rejects_overflow() -> None:
    with pytest.raises(PageLoadError):
        _load(
            {"id": "p", "title": "P", "containers": [
                {"title": "C", "cols": 12, "signals": [{"ref": "a", "row": 0, "col": 8, "w": 6}]}
            ]},
            {"a"},
        )


def test_authored_page_requires_containers() -> None:
    with pytest.raises(PageLoadError):
        _load({"id": "p", "title": "P", "containers": []}, set())


def test_generated_page_must_be_empty() -> None:
    # A generated page is filled at runtime; declaring containers is an error.
    with pytest.raises(PageLoadError):
        _load(
            {"id": "auto", "title": "Auto", "generated": True, "containers": [
                {"title": "C", "cols": 12, "signals": []}
            ]},
            set(),
        )
    ok = _load({"id": "auto", "title": "Auto", "generated": True, "containers": []}, set())
    assert ok.generated is True and ok.containers == ()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pages_loader.py -q`
Expected: FAIL — `ImportError: cannot import name 'Page'` (and `load_page`).

- [ ] **Step 3: Add the new model + loader (keep old symbols for now)**

Append to `src/pgntui/containers/loader.py` (do NOT delete `Container`/`GroupHeader`/`load_container` yet — Task 7 removes them; temporarily there will be two `Container` names, so name the new container class `Container` is a conflict — instead add the new classes under final names and rename the OLD `Container`→`_LegacyContainer` in this step to avoid the clash):

```python
class PageLoadError(ValueError):
    """Raised when a page JSON document is invalid."""


@dataclass(frozen=True, slots=True)
class Container:
    """A titled box that owns a grid of signal placements (container-relative)."""

    title: str
    cols: int
    signals: tuple[SignalPlacement, ...]


@dataclass(frozen=True, slots=True)
class Page:
    id: str
    title: str
    containers: tuple[Container, ...] = ()
    instances: tuple[InstanceOption, ...] = ()
    generated: bool = False


def _parse_container(raw: dict, known_signal_ids: set[str], source: str) -> Container:
    try:
        title = raw["title"]
    except KeyError as e:
        raise PageLoadError(f"{source}: container missing key {e}") from e
    cols = int(raw.get("cols", 12))
    if cols <= 0:
        raise PageLoadError(f"{source}: container {title!r} cols must be positive")
    placements: list[SignalPlacement] = []
    occupied: dict[tuple[int, int], str] = {}
    for item in raw.get("signals", []):
        ref = item["ref"]
        if ref not in known_signal_ids:
            raise PageLoadError(f"{source}: unknown signal ref {ref!r}")
        row, col, w = int(item["row"]), int(item["col"]), int(item["w"])
        if row < 0 or col < 0 or w <= 0:
            raise PageLoadError(f"{source}: ref {ref!r} has invalid geometry")
        if col + w > cols:
            raise PageLoadError(f"{source}: ref {ref!r} overflows container (cols={cols})")
        for c in range(col, col + w):
            cell = (row, c)
            if cell in occupied:
                raise PageLoadError(
                    f"{source}: {ref!r} overlaps {occupied[cell]!r} at row={row} col={c}"
                )
            occupied[cell] = ref
        placements.append(SignalPlacement(ref=ref, row=row, col=col, w=w))
    return Container(title=title, cols=cols, signals=tuple(placements))


def load_page(path: Path, known_signal_ids: set[str]) -> Page:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PageLoadError(f"{path}: invalid JSON: {e}") from e
    try:
        pid, title = payload["id"], payload["title"]
    except KeyError as e:
        raise PageLoadError(f"{path}: missing key {e}") from e
    generated = bool(payload.get("generated", False))
    raw_containers = payload.get("containers", [])
    if generated and raw_containers:
        raise PageLoadError(f"{path}: generated page must declare no containers")
    if not generated and not raw_containers:
        raise PageLoadError(f"{path}: page {pid!r} has no containers")
    containers = tuple(_parse_container(c, known_signal_ids, str(path)) for c in raw_containers)
    instances: list[InstanceOption] = []
    for item in payload.get("instances", []):
        try:
            instances.append(InstanceOption(id=int(item["id"]), label=str(item["label"])))
        except (KeyError, TypeError, ValueError) as e:
            raise PageLoadError(f"{path}: invalid instance entry {item!r}: {e}") from e
    return Page(
        id=pid,
        title=title,
        containers=containers,
        instances=tuple(instances),
        generated=generated,
    )
```

Also in this step, rename the EXISTING `class Container` to `class _LegacyContainer` and the EXISTING `load_container` return annotation accordingly, and rename `ContainerLoadError`'s references inside `load_container` are fine (keep `ContainerLoadError`). Update `__all__` to add `Container, Page, PageLoadError, load_page` (keep the legacy names too for now). `SignalPlacement` and `InstanceOption` are reused unchanged.

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pages_loader.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Confirm nothing else broke + commit**

Run: `.venv/Scripts/python.exe -m pytest -q` (Expected: all pass — old code untouched), then `.venv/Scripts/python.exe -m ruff check src/pgntui/containers/loader.py tests/test_pages_loader.py`.

```bash
git add src/pgntui/containers/loader.py tests/test_pages_loader.py
git commit -m "feat(loader): add Page/Container nested model + load_page (additive)"
```

---

## Task 2: Workspace migrator (old flat → new nested)

**Files:**
- Create: `src/pgntui/containers/migrate.py`
- Test: `tests/test_migrate_workspace.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_migrate_workspace.py
from __future__ import annotations

from pgntui.containers.migrate import migrate_page_dict


def test_groups_become_containers_with_relative_rows() -> None:
    old = {
        "id": "engine", "title": "Engine", "cols": 12,
        "instances": [{"id": 0, "label": "Stb"}],
        "groups": [{"title": "Drive", "row": 1}, {"title": "Oil", "row": 4}],
        "signals": [
            {"ref": "rpm", "row": 0, "col": 0, "w": 12},     # leading (before first group)
            {"ref": "boost", "row": 2, "col": 0, "w": 6},    # under Drive
            {"ref": "tilt", "row": 2, "col": 6, "w": 6},     # under Drive
            {"ref": "oilp", "row": 5, "col": 0, "w": 6},     # under Oil
        ],
    }
    new = migrate_page_dict(old)
    assert new["id"] == "engine"
    assert new["instances"] == [{"id": 0, "label": "Stb"}]
    assert "groups" not in new and "signals" not in new
    titles = [c["title"] for c in new["containers"]]
    assert titles == ["Engine", "Drive", "Oil"]  # leading bucket titled by page
    drive = new["containers"][1]
    assert drive["cols"] == 12
    # rows rebased to start at 0 within the container
    assert sorted(s["row"] for s in drive["signals"]) == [0, 0]
    assert {s["ref"] for s in drive["signals"]} == {"boost", "tilt"}


def test_no_groups_becomes_single_container() -> None:
    old = {"id": "main", "title": "Main", "cols": 12, "signals": [
        {"ref": "a", "row": 0, "col": 0, "w": 6}, {"ref": "b", "row": 1, "col": 0, "w": 6}]}
    new = migrate_page_dict(old)
    assert [c["title"] for c in new["containers"]] == ["Main"]
    assert len(new["containers"][0]["signals"]) == 2


def test_already_new_format_is_passed_through() -> None:
    new_in = {"id": "x", "title": "X", "containers": [
        {"title": "C", "cols": 12, "signals": [{"ref": "a", "row": 0, "col": 0, "w": 6}]}]}
    assert migrate_page_dict(new_in) == new_in
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrate_workspace.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'pgntui.containers.migrate'`.

- [ ] **Step 3: Implement the migrator**

```python
# src/pgntui/containers/migrate.py
"""Convert old flat container files (groups + page-absolute signals) into the
new nested Page → Container → Signal schema. Pure dict transforms + thin file
helpers so the conversion is unit-testable without Textual or a real workspace.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def migrate_page_dict(doc: dict[str, Any]) -> dict[str, Any]:
    """Return ``doc`` in the new nested schema. New-format docs pass through."""
    if "containers" in doc:  # already migrated
        return doc
    cols = int(doc.get("cols", 12))
    groups = sorted(doc.get("groups", []), key=lambda g: int(g["row"]))
    signals = list(doc.get("signals", []))

    def bucket_index(row: int) -> int | None:
        idx: int | None = None
        for i, g in enumerate(groups):
            if int(g["row"]) <= row:
                idx = i
            else:
                break
        return idx

    buckets: dict[int | None, list[dict[str, Any]]] = {}
    for s in signals:
        buckets.setdefault(bucket_index(int(s["row"])), []).append(s)

    containers: list[dict[str, Any]] = []

    def make_container(title: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        base = min(int(s["row"]) for s in items)
        return {
            "title": title,
            "cols": cols,
            "signals": [
                {"ref": s["ref"], "row": int(s["row"]) - base, "col": int(s["col"]), "w": int(s["w"])}
                for s in sorted(items, key=lambda s: (int(s["row"]), int(s["col"])))
            ],
        }

    # Leading (group-less) signals first, titled by the page (or "Signals").
    if buckets.get(None):
        containers.append(make_container(doc.get("title", "Signals"), buckets[None]))
    for i, g in enumerate(groups):
        if buckets.get(i):
            containers.append(make_container(g["title"], buckets[i]))
    if not containers:  # no signals at all — keep one empty container so it loads
        containers.append({"title": doc.get("title", "Signals"), "cols": cols, "signals": []})

    out: dict[str, Any] = {"id": doc["id"], "title": doc["title"], "containers": containers}
    if doc.get("instances"):
        out["instances"] = doc["instances"]
    return out


def migrate_workspace(workspace: Path) -> int:
    """Migrate every old-format file under ``workspace/containers`` in place.

    Backs originals up to ``containers.bak-flat/``. Idempotent: new-format files
    are rewritten unchanged. Returns the number of files converted (changed).
    """
    cdir = Path(workspace) / "containers"
    if not cdir.is_dir():
        return 0
    backup = Path(workspace) / "containers.bak-flat"
    converted = 0
    for path in sorted(cdir.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if "containers" in doc:
            continue
        backup.mkdir(exist_ok=True)
        (backup / path.name).write_text(json.dumps(doc, indent=2), encoding="utf-8")
        path.write_text(json.dumps(migrate_page_dict(doc), indent=2) + "\n", encoding="utf-8")
        converted += 1
    return converted
```

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrate_workspace.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/pgntui/containers/migrate.py tests/test_migrate_workspace.py
git commit -m "feat(migrate): old flat -> nested Page schema converter"
```

---

## Task 3: `PageView` renderer

**Files:**
- Modify: `src/pgntui/containers/screen.py`
- Test: `tests/test_page_view.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_page_view.py
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from pgntui.containers.loader import Container, Page, SignalPlacement
from pgntui.containers.screen import GroupBox, PageView
from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget
from pgntui.themes.loader import load_builtin


def _signals() -> dict:
    return {"rpm": AnalogIn(id="rpm", type="analog_in", title="RPM",
                            pgn=127488, field="Engine Speed", min=0, max=6000)}


def _page() -> Page:
    return Page(id="eng", title="Engine", containers=(
        Container(title="Drive", cols=12, signals=(SignalPlacement("rpm", 0, 0, 12),)),
    ))


class _Host(App[None]):
    def compose(self) -> ComposeResult:
        yield PageView(page=_page(), signals=_signals(), write_enabled=False,
                       theme=load_builtin("dark"))


@pytest.mark.asyncio
async def test_pageview_renders_container_as_titled_box() -> None:
    async with _Host().run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        boxes = list(pilot.app.query(GroupBox))
        assert len(boxes) == 1
        assert str(boxes[0].border_title) == "Drive"
        w = pilot.app.query_one(AnalogInWidget)
        assert w.region.height == 1 and w.region.width > 0
        assert w in boxes[0].walk_children()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_page_view.py -q`
Expected: FAIL — `ImportError: cannot import name 'PageView'`.

- [ ] **Step 3: Add `PageView` (keep `ContainerView` for now)**

In `src/pgntui/containers/screen.py`, add imports `from pgntui.containers.loader import Container, Page` (alongside existing) and add this class after `ContainerView`:

```python
class PageView(Widget):
    """Renders one Page: an optional page-level instance header, then a vertical
    scroll of its Containers, each a titled GroupBox wrapping its own grid."""

    DEFAULT_CSS = """
    PageView { height: 1fr; layout: vertical; overflow-y: auto; overflow-x: hidden; }
    PageView Grid { grid-rows: 1; grid-gutter: 0; height: auto; }
    PageView AnalogInWidget, PageView AnalogOutWidget,
    PageView DigitalInWidget, PageView DigitalOutWidget, PageView GroupRule { height: 1; }
    PageView GroupBox {
        height: auto;
        border: solid $accent;
        border-title-color: $accent; border-title-style: bold; border-title-align: left;
        padding: 0 1; margin: 0 0 1 0;
    }
    """

    def __init__(self, page: Page, signals: dict[str, Signal], write_enabled: bool,
                 theme: Theme | None = None) -> None:
        super().__init__()
        self.page = page
        self.signals = signals
        self.write_enabled = write_enabled
        self.theme_def = theme
        self.widgets: dict[str, Widget] = {}
        self._spans: list[tuple[Widget, int]] = []
        self.active_index = 0
        self._instance_header: GroupRule | None = None

    @property
    def active_instance_id(self) -> int | None:
        if not self.page.instances:
            return None
        return self.page.instances[self.active_index].id

    def _instance_label(self, index: int) -> str:
        opt = self.page.instances[index]
        return f"◀ {opt.label} ({opt.id}) ▶"

    def set_active_instance(self, index: int) -> None:
        if not self.page.instances:
            return
        self.active_index = index % len(self.page.instances)
        if self._instance_header is not None:
            self._instance_header.set_title(self._instance_label(self.active_index))
        for widget in self.widgets.values():
            if isinstance(widget, AnalogInWidget):
                widget.update_value(widget.signal.min)
            elif isinstance(widget, DigitalInWidget):
                widget.update_value(0)

    def compose(self) -> ComposeResult:
        if self.page.instances:
            self._instance_header = GroupRule(self._instance_label(self.active_index),
                                              theme=self.theme_def)
            yield self._instance_header
        for ci, container in enumerate(self.page.containers):
            grid = self._build_grid(container, f"grid-{self.page.id}-{ci}")
            box = GroupBox(grid, id=f"box-{self.page.id}-{ci}")
            box.border_title = container.title
            yield box

    def _build_grid(self, container: Container, grid_id: str) -> Grid:
        ordered = sorted(container.signals, key=lambda p: (p.row, p.col))
        children: list[Widget] = []
        for p in ordered:
            w = _make_widget(self.signals[p.ref], self.write_enabled, theme=self.theme_def)
            self.widgets[p.ref] = w
            self._spans.append((w, p.w))
            children.append(w)
        grid = Grid(*children, id=grid_id)
        grid.styles.grid_size_columns = container.cols
        return grid

    def on_mount(self) -> None:
        for widget, span in self._spans:
            widget.styles.column_span = span

    def apply_theme(self, theme: Theme) -> None:
        self.theme_def = theme
        if self._instance_header is not None:
            self._instance_header.theme_def = theme
            self._instance_header.refresh()
        for widget in self.widgets.values():
            widget.theme_def = theme  # type: ignore[attr-defined]
            widget.refresh()
```

Add `"PageView"` to `__all__`.

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_page_view.py -q`
Expected: PASS (1 test). Then `.venv/Scripts/python.exe -m pytest -q` — all still pass.

- [ ] **Step 5: Commit**

```bash
git add src/pgntui/containers/screen.py tests/test_page_view.py
git commit -m "feat(screen): add PageView rendering Page -> Container boxes (additive)"
```

---

## Task 4: Flip `app.py` + `__main__.py` to Pages

**Files:**
- Modify: `src/pgntui/app.py`, `src/pgntui/__main__.py`
- Test: `tests/test_app_empty_welcome.py`

- [ ] **Step 1: Update the welcome/legacy test to the new param name**

In `tests/test_app_empty_welcome.py`, change `PgntuiApp(theme=..., container_titles=["Engine"])` to `PgntuiApp(theme=..., page_titles=["Engine"])` and `PgntuiApp(theme=..., containers=[])` to `PgntuiApp(theme=..., pages=[])` (three call sites).

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_app_empty_welcome.py -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'pages'`.

- [ ] **Step 3: Update `app.py`**

In `src/pgntui/app.py`:
1. Imports: replace `from pgntui.containers.screen import ContainerView` with `from pgntui.containers.screen import PageView`; add `from textual.containers import VerticalScroll`; replace `from pgntui.containers.loader import Container` with `from pgntui.containers.loader import Page`.
2. Constructor: rename param `containers: list[Container] | None` → `pages: list[Page] | None`, `container_titles` → `page_titles`; store `self._pages = pages or []`, `self._page_titles = page_titles`. Replace `self._view_pairs: list[tuple[Container, ContainerView]]` with `self._page_views: list[tuple[Page, PageView]]`.
3. `compose()` — replace the per-container tab loop with one TabPane per Page (Auto tab is Phase 2, not added here):

```python
    def compose(self) -> ComposeResult:
        yield TopBar()
        with Vertical():
            with TabbedContent(id="tabs"):
                if self._page_titles is not None:
                    for title in self._page_titles:
                        with TabPane(title):
                            yield Static(title, classes="signal-title")
                else:
                    for page in self._pages:
                        with TabPane(page.title, id=f"tab-{page.id}"):
                            view = PageView(page=page, signals=self._signals,
                                            write_enabled=self._write_enabled, theme=self._theme)
                            self._page_views.append((page, view))
                            yield view
                with TabPane("Debug", id="debug"):
                    if not self._pages and self._page_titles is None:
                        yield Static(_WELCOME_TEXT, id="welcome", markup=True)
                    self._debug_log = DebugLog(highlight=False, markup=False, wrap=False, id="debug-log")
                    yield self._debug_log
                    self._debug_aggregate = DebugAggregate(id="debug-aggregate")
                    self._debug_aggregate.display = False
                    yield self._debug_aggregate
            yield Static(
                "[Tab] Page  [ [ / ] ] Instance  [D] Debug  [G] Group  [R] Rec  "
                "[C] Connection  [S] Config  [A] About  [Q] Quit",
                id="hotkey-strip", markup=False,
            )
            yield Static("status: idle", id="status-bar", markup=False)
```

4. Replace every other `self._view_pairs` reference with `self._page_views`, and `ContainerView` with `PageView` (e.g. in `_wire_write_callbacks`, `apply_theme`, the routing/`_dispatch` loop, and `_view_of_widget` typing).
5. `_active_view()` — page-level: return the active tab's PageView:

```python
    def _active_view(self) -> PageView | None:
        try:
            active = self.query_one(TabbedContent).active
        except Exception:  # pragma: no cover — pre-mount
            return None
        for page, view in self._page_views:
            if f"tab-{page.id}" == active:
                return view
        return None
```

6. `_cycle_instance` — update the guard to use `view.page.instances` and the status text to `"this page has no instances to switch"`; the rest is unchanged (`view.set_active_instance`, label from `view.page.instances`).

- [ ] **Step 4: Update `__main__.py`**

In `src/pgntui/__main__.py`:
- Rename `discover_containers` → `discover_pages`, returning `list[Page]` via `load_page` (import `Page, load_page` from `pgntui.containers.loader`; drop `Container, load_container`).
- In `_build_app`, rename local `containers` → `pages` and pass `pages=pages` to `PgntuiApp`.

```python
def discover_pages(workspace: Path, signal_ids: set[str]) -> list[Page]:
    c_dir = workspace / "containers"
    if not c_dir.is_dir():
        return []
    return [load_page(p, signal_ids) for p in sorted(c_dir.glob("*.json"))]
```

- [ ] **Step 5: Run the welcome test, then full suite**

Run: `.venv/Scripts/python.exe -m pytest tests/test_app_empty_welcome.py -q`
Expected: PASS.

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: FAILURES in `test_app_container_visible.py`, `test_main_replay.py`, `test_instance_switch.py`, `test_container_groups.py` (they still use old schema / `ContainerView` / `tab-<container>` and the example files are still old-format). These are fixed in Task 5. Do not commit yet if red; proceed to Task 5 and commit together.

> Note: `__init__` still annotates `containers`/`ContainerView` nowhere now; ensure no stray references remain via `grep -n "ContainerView\|_view_pairs\|container_titles\|discover_containers" src/pgntui/app.py src/pgntui/__main__.py` → expect no hits.

---

## Task 5: Migrate bundled examples + update example-dependent tests

**Files:**
- Modify: `src/pgntui/examples/containers/{1-nav,2-engine,3-main}.json`
- Modify: `tests/test_app_container_visible.py`, `tests/test_main_replay.py`, `tests/test_instance_switch.py`, `tests/test_container_groups.py`

- [ ] **Step 1: Convert the example files with the migrator**

Run (one-off dev conversion using the Task 2 code):

```bash
.venv/Scripts/python.exe -c "from pgntui.containers.migrate import migrate_workspace; from pathlib import Path; print('converted', migrate_workspace(Path('src/pgntui/examples')))"
```

Expected: `converted 3`. Then **delete** the generated backup so it doesn't ship: `rm -rf src/pgntui/examples/containers.bak-flat`.

- [ ] **Step 2: Polish `2-engine.json`** so the leading `engine_rpm` lives in the Drive container instead of a generic leading box. Open `src/pgntui/examples/containers/2-engine.json` and move the `engine_rpm` placement into the `"Drive"` container's `signals` (row 0, col 0, w 12) and push Drive's other rows down by 1; delete the leading `"Engine"`-titled container the migrator produced. Final `containers[0]` must be:

```jsonc
{ "title": "Drive", "cols": 12, "signals": [
  { "ref": "engine_rpm", "row": 0, "col": 0, "w": 12 },
  { "ref": "boost_pressure", "row": 1, "col": 0, "w": 6 },
  { "ref": "tilt_trim", "row": 1, "col": 6, "w": 6 } ] }
```

- [ ] **Step 3: Verify the examples load under the new loader**

Run:
```bash
.venv/Scripts/python.exe -c "from pgntui.containers.loader import load_page; from pathlib import Path; import glob; [print(load_page(Path(f), {'engine_rpm','boost_pressure','tilt_trim','oil_pressure','oil_temperature','engine_temp','alternator_voltage','fuel_rate','total_hours','coolant_pressure','fuel_pressure','engine_load','engine_torque','heading_mag','true_heading','deviation','variation','latitude','longitude','speed','speed_sog','course_cog','rate_of_turn','depth','rudder','wind_direction','wind_speed','current_direction','current_speed','water_temp','target_heading','bilge_alarm','anchor_light'}).title) for f in sorted(glob.glob('src/pgntui/examples/containers/*.json'))]"
```
Expected: prints `Nav`, `Engine`, `Main` with no `PageLoadError`. (If a ref is missing, the signal id list above is the full example set from `examples/signals/`.)

- [ ] **Step 4: Update the example-dependent tests**

`tests/test_app_container_visible.py` — iterate `app._page_views`, set `tabs.active = f"tab-{page.id}"`:

```python
        assert app._page_views, "example workspace produced no page views"
        for page, view in app._page_views:
            tabs.active = f"tab-{page.id}"
            await pilot.pause()
            assert view.widgets, f"page {page.id} has no widgets"
            for ref, w in view.widgets.items():
                assert w.region.height > 0, f"{page.id}/{ref} collapsed to zero height"
                assert w.region.width > 0, f"{page.id}/{ref} collapsed to zero width"
```

`tests/test_main_replay.py`:
- `test_main_replay_runs_app_with_containers`: `captured["containers"]` still reads `self._pages` now — change to `captured["pages"] = [p.id for p in self._pages]` and assert `captured["pages"] == ["engine", "nav"]`.
- `test_replay_app_composes_tabpane_per_container`: rename to `_per_page`; assert `"tab-engine"`, `"tab-nav"`, `"debug"` in tab ids (unchanged ids, still valid).
- Ensure the fixture containers `tests/fixtures/e2e_containers/*.json` are new-schema. Convert them: `.venv/Scripts/python.exe -c "from pgntui.containers.migrate import migrate_workspace; from pathlib import Path; migrate_workspace(Path('tests/fixtures'))"` is NOT valid (fixtures dir has no `containers/` subdir named that way) — instead convert each file in place with `migrate_page_dict`:

```bash
.venv/Scripts/python.exe -c "import json,glob; from pgntui.containers.migrate import migrate_page_dict; [open(f,'w',encoding='utf-8').write(json.dumps(migrate_page_dict(json.load(open(f,encoding='utf-8'))),indent=2)) for f in glob.glob('tests/fixtures/e2e_containers/*.json')]"
```

`tests/test_instance_switch.py`:
- `_engine_container()` returns a `Container` today — change it to build a `Page`: import `Page, Container, SignalPlacement` and return
  `Page(id="engine", title="Engine", instances=(...), containers=(Container(title="Drive", cols=12, signals=(SignalPlacement("rpm",0,0,12),)),))`.
- `_app()` passes `containers=[_engine_container()]` → `pages=[_engine_page()]`.
- `app.query_one(ContainerView)` → `app.query_one(PageView)` (import `PageView`); `view._instance_header` and `view.active_instance_id` work unchanged; `view.widgets["rpm"]` unchanged.

`tests/test_container_groups.py`:
- The loader-level tests (`test_loader_parses_groups`, `test_loader_rejects_group_row_collision_with_signal`, `test_loader_defaults_no_groups`) target the OLD `load_container`/`GroupHeader`, which are removed in Task 7. **Move** the still-relevant rendering test (`test_rows_are_single_line_and_group_renders_as_titled_box`) into `tests/test_page_view.py` as a Page-based test, and **delete** `tests/test_container_groups.py` (its loader behaviors are now covered by `tests/test_pages_loader.py`). `test_group_rule_text_spans_and_titles` (tests `GroupRule`) moves to `tests/test_page_view.py` too (GroupRule is retained).

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass. Then ruff + mypy on changed files.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(app): render Pages as tabs; migrate examples to nested schema"
```

---

## Task 6: `--migrate-workspace` CLI flag

**Files:**
- Modify: `src/pgntui/__main__.py`
- Test: `tests/test_migrate_workspace.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/test_migrate_workspace.py`:

```python
from pathlib import Path
import json
from pgntui.__main__ import main


def test_cli_migrate_workspace(tmp_path: Path) -> None:
    cdir = tmp_path / "containers"
    cdir.mkdir()
    (cdir / "a.json").write_text(json.dumps(
        {"id": "a", "title": "A", "cols": 12,
         "signals": [{"ref": "x", "row": 0, "col": 0, "w": 6}]}), encoding="utf-8")
    rc = main(["--workspace", str(tmp_path), "--migrate-workspace"])
    assert rc == 0
    out = json.loads((cdir / "a.json").read_text(encoding="utf-8"))
    assert "containers" in out and "signals" not in out
    assert (tmp_path / "containers.bak-flat" / "a.json").exists()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrate_workspace.py::test_cli_migrate_workspace -q`
Expected: FAIL — `--migrate-workspace` is an unknown arg (SystemExit 2).

- [ ] **Step 3: Implement the flag**

In `build_parser()` add: `p.add_argument("--migrate-workspace", action="store_true", help="convert old-format container files in --workspace to the new schema and exit")`.

In `main()`, after `workspace = resolve_workspace(args.workspace)` and before loading config, add:

```python
    if args.migrate_workspace:
        from pgntui.containers.migrate import migrate_workspace
        n = migrate_workspace(workspace)
        print(f"migrated {n} container file(s) under {workspace}")
        return 0
```

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrate_workspace.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/pgntui/__main__.py tests/test_migrate_workspace.py
git commit -m "feat(cli): --migrate-workspace converts old container files in place"
```

---

## Task 7: Remove dead old symbols

**Files:**
- Modify: `src/pgntui/containers/loader.py`, `src/pgntui/containers/screen.py`

- [ ] **Step 1: Find remaining references**

Run: `grep -rn "ContainerView\|ContainerScreen\|_LegacyContainer\|GroupHeader\|load_container\|ContainerLoadError\|discover_containers" src/ tests/`
Expected: hits only in `loader.py`/`screen.py` definitions (and `screen.py`'s `__all__`). If any test still references them, it was missed in Task 5 — fix it.

- [ ] **Step 2: Delete the old symbols**

In `loader.py`: remove `_LegacyContainer` (old `Container`), `GroupHeader`, `load_container`, `ContainerLoadError`; clean `__all__` to `["Container", "InstanceOption", "Page", "PageLoadError", "SignalPlacement", "load_page"]`.

In `screen.py`: remove `ContainerView` and `ContainerScreen`; keep `GroupBox`, `GroupRule`, `PageView`, `_make_widget`; set `__all__ = ["GroupBox", "GroupRule", "PageView"]`. Remove the now-unused `from pgntui.containers.loader import ...` names that are gone.

- [ ] **Step 3: Run the full suite + lint + types**

Run: `.venv/Scripts/python.exe -m pytest -q` (Expected: all pass.)
Run: `.venv/Scripts/python.exe -m ruff check src tests` (Expected: All checks passed.)
Run: `.venv/Scripts/python.exe -m mypy src/pgntui` (Expected: Success.)

- [ ] **Step 4: Manual render check (optional but recommended)**

Use the render-to-text helper pattern from the session (build the example app, activate `tab-engine`/`tab-main`, dump screen text) and confirm: Engine RPM is now inside the Drive box, and Main shows titled containers — no naked signals, no box-less page.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(containers): remove legacy Container/GroupHeader/ContainerView"
```

---

## Self-Review notes

- **Spec coverage:** rename (T1,T3,T4,T7), new schema + validation (T1), migrator + CLI (T2,T6), render Pages/Containers (T3,T4), page-level instances (T3,T4), example migration (T5), tests (every task). Auto page is explicitly Phase 2 — not in this plan.
- **Type consistency:** `Page(id,title,containers,instances,generated)`, `Container(title,cols,signals)`, `SignalPlacement(ref,row,col,w)`, `load_page`, `PageView(page,signals,write_enabled,theme)`, `PageLoadError`, `migrate_page_dict`, `migrate_workspace`, `discover_pages`, app param `pages`/`page_titles`, `self._page_views` — used consistently across tasks.
- **Ordering:** additive (T1–T3) keeps the suite green; the flip (T4) is intentionally red until T5 migrates examples/tests; cleanup (T7) ends green.
