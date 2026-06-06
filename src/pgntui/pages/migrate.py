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

    def make_container(title: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        base = min(int(s["row"]) for s in items)
        return {
            "title": title,
            "cols": cols,
            "signals": [
                {
                    "ref": s["ref"],
                    "row": int(s["row"]) - base,
                    "col": int(s["col"]),
                    "w": int(s["w"]),
                }
                for s in sorted(items, key=lambda s: (int(s["row"]), int(s["col"])))
            ],
        }

    containers: list[dict[str, Any]] = []
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
    are left untouched. Returns the number of files converted (changed).
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


__all__ = ["migrate_page_dict", "migrate_workspace"]
