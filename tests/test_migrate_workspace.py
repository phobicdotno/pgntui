from __future__ import annotations

import json
from pathlib import Path

from pgntui.__main__ import main
from pgntui.pages.migrate import migrate_page_dict


def test_groups_become_containers_with_relative_rows() -> None:
    old = {
        "id": "engine",
        "title": "Engine",
        "cols": 12,
        "instances": [{"id": 0, "label": "Stb"}],
        "groups": [{"title": "Drive", "row": 1}, {"title": "Oil", "row": 4}],
        "signals": [
            {"ref": "rpm", "row": 0, "col": 0, "w": 12},  # leading (before first group)
            {"ref": "boost", "row": 2, "col": 0, "w": 6},  # under Drive
            {"ref": "tilt", "row": 2, "col": 6, "w": 6},  # under Drive
            {"ref": "oilp", "row": 5, "col": 0, "w": 6},  # under Oil
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
    assert sorted(s["row"] for s in drive["signals"]) == [0, 0]
    assert {s["ref"] for s in drive["signals"]} == {"boost", "tilt"}


def test_no_groups_becomes_single_container() -> None:
    old = {
        "id": "main",
        "title": "Main",
        "cols": 12,
        "signals": [
            {"ref": "a", "row": 0, "col": 0, "w": 6},
            {"ref": "b", "row": 1, "col": 0, "w": 6},
        ],
    }
    new = migrate_page_dict(old)
    assert [c["title"] for c in new["containers"]] == ["Main"]
    assert len(new["containers"][0]["signals"]) == 2


def test_already_new_format_is_passed_through() -> None:
    new_in = {
        "id": "x",
        "title": "X",
        "containers": [
            {"title": "C", "cols": 12, "signals": [{"ref": "a", "row": 0, "col": 0, "w": 6}]}
        ],
    }
    assert migrate_page_dict(new_in) == new_in


def test_cli_migrate_workspace(tmp_path: Path) -> None:
    cdir = tmp_path / "containers"
    cdir.mkdir()
    (cdir / "a.json").write_text(
        json.dumps(
            {
                "id": "a",
                "title": "A",
                "cols": 12,
                "signals": [{"ref": "x", "row": 0, "col": 0, "w": 6}],
            }
        ),
        encoding="utf-8",
    )
    rc = main(["--workspace", str(tmp_path), "--migrate-workspace"])
    assert rc == 0
    out = json.loads((cdir / "a.json").read_text(encoding="utf-8"))
    assert "containers" in out and "signals" not in out
    assert (tmp_path / "containers.bak-flat" / "a.json").exists()
