"""Theme JSON loader and Textual CSS generator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

REQUIRED_COLORS = (
    "bg",
    "fg",
    "fg_dim",
    "accent",
    "ok",
    "warn",
    "alarm",
    "border",
    "title_bg",
    "title_fg",
    "bar_track",
    "bar_fill",
    "bar_warn",
    "bar_alarm",
)


class ThemeLoadError(ValueError):
    """Raised when a theme JSON document is invalid."""


@dataclass(frozen=True, slots=True)
class Gradient:
    target: str
    stops: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Theme:
    id: str
    title: str
    colors: dict[str, str]
    glyphs: dict[str, str]
    styles: dict[str, str]
    gradients: tuple[Gradient, ...] = ()
    animate: bool = False
    animate_fps: int = 4


def _parse(payload: dict[str, Any], source: str) -> Theme:
    try:
        tid = payload["id"]
        title = payload["title"]
        colors = dict(payload["colors"])
    except KeyError as e:
        raise ThemeLoadError(f"{source}: missing key {e}") from e
    for c in REQUIRED_COLORS:
        if c not in colors:
            raise ThemeLoadError(f"{source}: missing color {c!r}")
    gradients = tuple(
        Gradient(target=g["target"], stops=tuple(g["stops"])) for g in payload.get("gradients", [])
    )
    return Theme(
        id=tid,
        title=title,
        colors=colors,
        glyphs=dict(payload.get("glyphs", {})),
        styles=dict(payload.get("styles", {})),
        gradients=gradients,
        animate=bool(payload.get("animate", False)),
        animate_fps=int(payload.get("animate_fps", 4)),
    )


def load_theme(path: Path) -> Theme:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ThemeLoadError(f"{path}: invalid JSON: {e}") from e
    return _parse(payload, str(path))


def load_builtin(name: str) -> Theme:
    try:
        with (
            resources.files("pgntui.themes.builtin")
            .joinpath(f"{name}.json")
            .open("r", encoding="utf-8") as fh
        ):
            payload = json.load(fh)
    except FileNotFoundError as e:
        raise ThemeLoadError(f"builtin theme {name!r} not found") from e
    return _parse(payload, f"builtin:{name}")


def to_textual_css(theme: Theme) -> str:
    c = theme.colors
    lines = [
        f"Screen {{ background: {c['bg']}; color: {c['fg']}; }}",
        f".signal-title {{ color: {c['title_fg']}; background: {c['title_bg']}; }}",
        f".signal-value {{ color: {c['fg']}; }}",
        f".signal-unit  {{ color: {c['fg_dim']}; }}",
        f".bar-track   {{ color: {c['bar_track']}; }}",
        f".bar-fill    {{ color: {c['bar_fill']}; }}",
        f".bar-warn    {{ color: {c['bar_warn']}; }}",
        f".bar-alarm   {{ color: {c['bar_alarm']}; }}",
        f".border-line {{ color: {c['border']}; }}",
        f".state-ok    {{ color: {c['ok']}; }}",
        f".state-warn  {{ color: {c['warn']}; }}",
        f".state-alarm {{ color: {c['alarm']}; }}",
        f".accent      {{ color: {c['accent']}; }}",
        f".disabled    {{ color: {c['fg_dim']}; }}",
    ]
    return "\n".join(lines) + "\n"


__all__ = [
    "Gradient",
    "Theme",
    "ThemeLoadError",
    "load_builtin",
    "load_theme",
    "to_textual_css",
]
