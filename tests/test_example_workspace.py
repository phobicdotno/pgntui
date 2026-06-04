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
    # Seven shipped defaults: four analog readouts plus one of each remaining
    # widget kind so the scaffold exercises the full UI surface.
    assert ids == {
        "engine_rpm",
        "speed",
        "depth",
        "water_temp",
        "target_heading",
        "bilge_alarm",
        "anchor_light",
    }
    # Containers reference signal ids that exist.
    main_container = load_container(ws / "containers" / "main.json", ids)
    refs = {p.ref for p in main_container.signals}
    assert refs.issubset(ids)
    assert main_container.cols == 12


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
