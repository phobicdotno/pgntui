"""Verify `pgntui --example` scaffolds a working workspace."""

from __future__ import annotations

from pathlib import Path

from pgntui.__main__ import main
from pgntui.containers.loader import load_container
from pgntui.signals.base import AnalogIn, AnalogOut, DigitalIn, DigitalOut, load_signals_dir


def test_example_creates_expected_files(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    rc = main(["--workspace", str(ws), "--example"])
    assert rc == 0
    assert (ws / "config.toml").is_file()
    assert (ws / "signals").is_dir()
    assert (ws / "containers").is_dir()
    signals = load_signals_dir(ws / "signals")
    ids = {s.id for s in signals}
    # The original seven defaults must still ship (one of each widget kind),
    # plus the Nav/Engine dashboard signals added on top.
    assert {
        "engine_rpm",
        "speed",
        "depth",
        "water_temp",
        "target_heading",
        "bilge_alarm",
        "anchor_light",
        "heading_mag",
        "speed_sog",
        "oil_pressure",
    }.issubset(ids)
    # Every container only references signal ids that exist, and the tab
    # order is nav, engine, main (numeric filename prefixes).
    container_paths = sorted((ws / "containers").glob("*.json"))
    assert [p.name for p in container_paths] == ["1-nav.json", "2-engine.json", "3-main.json"]
    for path in container_paths:
        container = load_container(path, ids)
        refs = {p.ref for p in container.signals}
        assert refs.issubset(ids)
        assert container.cols == 12


def test_example_includes_all_four_widget_types(tmp_path: Path) -> None:
    """Scaffolded workspace must contain at least one signal of each kind."""
    ws = tmp_path / "ws"
    rc = main(["--workspace", str(ws), "--example"])
    assert rc == 0
    signals = load_signals_dir(ws / "signals")
    kinds = {type(s) for s in signals}
    assert AnalogIn in kinds
    assert AnalogOut in kinds
    assert DigitalIn in kinds
    assert DigitalOut in kinds


def test_example_refuses_when_workspace_non_empty(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "stray.txt").write_text("hello")
    rc = main(["--workspace", str(ws), "--example"])
    assert rc == 2
    captured = capsys.readouterr()
    assert "refusing to overwrite" in captured.err


def test_example_works_with_brand_new_workspace_dir(tmp_path: Path) -> None:
    """An empty-but-existing workspace directory is allowed."""
    ws = tmp_path / "ws"
    ws.mkdir()  # empty dir is OK
    rc = main(["--workspace", str(ws), "--example"])
    assert rc == 0


def test_example_refuses_file_path(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    """Pointing --example at an existing file (not dir) errors cleanly."""
    tmp_file = tmp_path / "notadir.txt"
    tmp_file.write_text("oops")
    rc = main(["--workspace", str(tmp_file), "--example"])
    assert rc == 2
    captured = capsys.readouterr()
    assert "is a file" in captured.err
