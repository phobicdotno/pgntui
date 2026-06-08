"""Persisting driver port/speed back into config.toml."""

from __future__ import annotations

from pathlib import Path

from pgntui.config import load_config, write_driver_settings, write_layout

EXAMPLE = """\
[app]
theme = "dark"
write_enabled = false

[logging]
csv_dir = "logs"
record_dir = "recordings"

[driver]
name = "file-replay"

# Example Actisense NGT-1 configuration:
# [driver]
# name = "actisense-ngt1"
# port = "COM3"
"""


def test_write_layout_roundtrip_and_preserves_theme(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text(EXAMPLE, encoding="utf-8")
    write_layout(p, columns=2, groups=3, pages=2)
    cfg = load_config(p)
    assert cfg.layout_columns == 2
    assert cfg.layout_groups == 3
    assert cfg.layout_pages == 2
    # The existing theme key in [app] must survive the merge.
    assert cfg.theme == "dark"
    # Updating only one axis leaves the others intact.
    write_layout(p, groups=1)
    cfg2 = load_config(p)
    assert cfg2.layout_groups == 1
    assert cfg2.layout_columns == 2  # unchanged
    assert cfg2.theme == "dark"


def test_layout_defaults_when_absent(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text('[app]\ntheme = "dark"\n', encoding="utf-8")
    cfg = load_config(p)
    assert cfg.layout_columns is None  # authored layout
    assert cfg.layout_groups == 1
    assert cfg.layout_pages == 1


def test_write_updates_existing_driver_section(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text(EXAMPLE, encoding="utf-8")
    write_driver_settings(p, name="actisense-ngt1", port="COM4", baud=115200)
    cfg = load_config(p)
    assert cfg.driver_name == "actisense-ngt1"
    assert cfg.driver_options["port"] == "COM4"
    assert cfg.driver_options["baud"] == 115200
    text = p.read_text(encoding="utf-8")
    # Comments and other sections are preserved.
    assert "# Example Actisense NGT-1 configuration:" in text
    assert "[app]" in text
    assert "[logging]" in text


def test_write_is_idempotent(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text(EXAMPLE, encoding="utf-8")
    write_driver_settings(p, name="actisense-ngt1", port="COM4", baud=115200)
    first = p.read_text(encoding="utf-8")
    write_driver_settings(p, name="actisense-ngt1", port="COM4", baud=115200)
    assert p.read_text(encoding="utf-8") == first


def test_write_creates_file_when_missing(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    write_driver_settings(p, name="actisense-ngt1", port="/dev/ttyUSB0", baud=230400)
    cfg = load_config(p)
    assert cfg.driver_name == "actisense-ngt1"
    assert cfg.driver_options["port"] == "/dev/ttyUSB0"
    assert cfg.driver_options["baud"] == 230400


def test_write_changes_port_without_duplicating_keys(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text(EXAMPLE, encoding="utf-8")
    write_driver_settings(p, name="actisense-ngt1", port="COM4", baud=115200)
    write_driver_settings(p, name="actisense-ngt1", port="COM7", baud=115200)
    text = p.read_text(encoding="utf-8")
    real_port_lines = [ln for ln in text.splitlines() if ln.strip().startswith("port =")]
    assert len(real_port_lines) == 1  # commented "# port =" not counted
    cfg = load_config(p)
    assert cfg.driver_options["port"] == "COM7"
