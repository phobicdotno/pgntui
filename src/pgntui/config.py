"""TOML config loader."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir


def _default_workspace() -> Path:
    """Return the OS-appropriate workspace directory.

    Linux  -> ``~/.config/pgntui`` (XDG)
    macOS  -> ``~/Library/Application Support/pgntui``
    Windows -> ``%APPDATA%/pgntui``
    """
    return Path(user_config_dir("pgntui"))


@dataclass(frozen=True, slots=True)
class Config:
    driver_name: str = "file-replay"
    driver_options: dict[str, Any] = field(default_factory=dict)
    write_enabled: bool = False
    theme: str = "dark"
    workspace: Path = field(default_factory=_default_workspace)
    csv_dir: str = "logs"
    record_dir: str = "recordings"


def load_config(path: Path) -> Config:
    """Load config from a TOML file.

    Missing file returns a default ``Config``. Malformed TOML is wrapped in a
    ``ValueError`` carrying the offending path so the CLI can print a friendly
    error instead of a raw traceback.
    """
    path = Path(path)
    if not path.exists():
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"{path}: TOML syntax error: {e}") from e
    driver = data.get("driver", {})
    app = data.get("app", {})
    logging_cfg = data.get("logging", {})
    driver_opts = {k: v for k, v in driver.items() if k != "name"}
    workspace_str = app.get("workspace")
    workspace = Path(workspace_str).expanduser() if workspace_str else _default_workspace()
    return Config(
        driver_name=driver.get("name", "file-replay"),
        driver_options=driver_opts,
        write_enabled=bool(app.get("write_enabled", False)),
        theme=app.get("theme", "dark"),
        workspace=workspace,
        csv_dir=logging_cfg.get("csv_dir", "logs"),
        record_dir=logging_cfg.get("record_dir", "recordings"),
    )


__all__ = ["Config", "load_config"]
