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
