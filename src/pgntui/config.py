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
    # Last-used layout, restored on launch. ``layout_columns`` is the signal
    # columns inside a box ([1]/[2]/[3]); None means the page's authored layout.
    # ``layout_groups`` is the box columns (Shift+1/2/3); ``layout_pages`` is the
    # section columns on the Main tab (F1/F2/F3). 1 = the default single column.
    layout_columns: int | None = None
    layout_groups: int = 1
    layout_pages: int = 1


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
        layout_columns=_as_cols(app.get("layout_columns")),
        layout_groups=_as_cols(app.get("layout_groups")) or 1,
        layout_pages=_as_cols(app.get("layout_pages")) or 1,
    )


def _as_cols(value: Any) -> int | None:
    """Coerce a saved layout value to 1/2/3, or None if absent/out of range."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 3 else None


def _toml_key(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("#") or "=" not in stripped:
        return ""
    return stripped.split("=", 1)[0].strip()


def write_driver_settings(path: Path, name: str, port: str, baud: int) -> None:
    """Persist ``[driver]`` ``name``/``port``/``baud`` into ``path``.

    Line-based so existing comments and other sections are preserved. The three
    keys are written directly under the ``[driver]`` header; any pre-existing
    (non-commented) copies elsewhere in that section are dropped. A missing file
    or missing ``[driver]`` section is created.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    new = {
        "name": f'name = "{name}"',
        "port": f'port = "{port}"',
        "baud": f"baud = {int(baud)}",
    }
    out: list[str] = []
    in_driver = False
    driver_found = False
    for line in text.splitlines():
        stripped = line.strip()
        is_header = stripped.startswith("[") and not stripped.startswith("#")
        if is_header and stripped == "[driver]":
            out.append(line)
            out.extend((new["name"], new["port"], new["baud"]))
            in_driver = True
            driver_found = True
            continue
        if is_header and in_driver:
            in_driver = False
        if in_driver and _toml_key(line) in ("name", "port", "baud"):
            continue  # drop the old key; the new value is already written
        out.append(line)
    if not driver_found:
        if out and out[-1].strip() != "":
            out.append("")
        out.append("[driver]")
        out.extend((new["name"], new["port"], new["baud"]))
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def write_theme(path: Path, theme_id: str) -> None:
    """Persist ``[app]`` ``theme = "<id>"`` into ``path``.

    Line-based so existing comments and other sections are preserved. Any
    pre-existing (non-commented) ``theme`` key in the ``[app]`` section is
    replaced; a missing file or missing ``[app]`` section is created.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    new_line = f'theme = "{theme_id}"'
    out: list[str] = []
    in_app = False
    app_found = False
    for line in text.splitlines():
        stripped = line.strip()
        is_header = stripped.startswith("[") and not stripped.startswith("#")
        if is_header and stripped == "[app]":
            out.append(line)
            out.append(new_line)
            in_app = True
            app_found = True
            continue
        if is_header and in_app:
            in_app = False
        if in_app and _toml_key(line) == "theme":
            continue  # drop the old key; the new value is already written
        out.append(line)
    if not app_found:
        if out and out[-1].strip() != "":
            out.append("")
        out.append("[app]")
        out.append(new_line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def write_layout(
    path: Path,
    *,
    columns: int | None = None,
    groups: int | None = None,
    pages: int | None = None,
) -> None:
    """Persist the last-used layout into ``[app]`` (``layout_columns`` /
    ``layout_groups`` / ``layout_pages``), so it is restored on the next launch.

    Line-based so existing comments, the ``theme`` key, and other sections are
    preserved. Only the provided (non-None) keys are written; any pre-existing
    copies of *those* keys in ``[app]`` are replaced. A missing file or missing
    ``[app]`` section is created.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    new: dict[str, str] = {}
    if columns is not None:
        new["layout_columns"] = f"layout_columns = {int(columns)}"
    if groups is not None:
        new["layout_groups"] = f"layout_groups = {int(groups)}"
    if pages is not None:
        new["layout_pages"] = f"layout_pages = {int(pages)}"
    if not new:
        return
    out: list[str] = []
    in_app = False
    app_found = False
    for line in text.splitlines():
        stripped = line.strip()
        is_header = stripped.startswith("[") and not stripped.startswith("#")
        if is_header and stripped == "[app]":
            out.append(line)
            out.extend(new.values())
            in_app = True
            app_found = True
            continue
        if is_header and in_app:
            in_app = False
        if in_app and _toml_key(line) in new:
            continue  # drop the old key; the new value is already written
        out.append(line)
    if not app_found:
        if out and out[-1].strip() != "":
            out.append("")
        out.append("[app]")
        out.extend(new.values())
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


__all__ = [
    "Config",
    "load_config",
    "write_driver_settings",
    "write_layout",
    "write_theme",
]
