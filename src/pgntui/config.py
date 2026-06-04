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
