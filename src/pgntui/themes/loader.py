"""Theme JSON loader and Textual CSS generator."""

from __future__ import annotations

import json
import re
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

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


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


def _validate_stops(source: str, target: str, stops: list[str]) -> None:
    if len(stops) < 2:
        raise ThemeLoadError(
            f"{source}: gradient {target!r}: must have at least 2 stops, got {len(stops)}"
        )
    for s in stops:
        if not isinstance(s, str) or not _HEX_COLOR.match(s):
            raise ThemeLoadError(f"{source}: gradient {target!r}: invalid hex color {s!r}")


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
    gradient_list: list[Gradient] = []
    for g in payload.get("gradients", []):
        target = g["target"]
        stops = list(g["stops"])
        _validate_stops(source, target, stops)
        gradient_list.append(Gradient(target=target, stops=tuple(stops)))
    gradients = tuple(gradient_list)
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
        payload = json.loads(path.read_text(encoding="utf-8"))
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


def list_builtin() -> list[tuple[str, str]]:
    """Return ``(title, id)`` pairs for every bundled theme, sorted by title.

    Used by the in-app config menu to populate the theme picker. Reads only the
    ``id``/``title`` keys leniently so a malformed extra file can't break the
    whole list; full validation still happens in ``load_builtin`` on selection.
    """
    out: list[tuple[str, str]] = []
    for entry in resources.files("pgntui.themes.builtin").iterdir():
        name = entry.name
        if not name.endswith(".json"):
            continue
        try:
            payload = json.loads(entry.read_text(encoding="utf-8"))
            out.append((str(payload["title"]), str(payload["id"])))
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    out.sort(key=lambda pair: pair[0].lower())
    return out


def to_textual_theme(theme: Theme) -> Any:
    """Build a Textual ``Theme`` from a pgntui theme.

    Maps pgntui's color roles onto Textual's chrome theme so the header,
    tab bar, footer and scrollbars match the rest of the UI. Imported
    lazily so the loader has no hard dependency on Textual.
    """
    from textual.theme import Theme as TextualTheme

    c = theme.colors
    # ``light`` is the only builtin that is a light theme; everything else is
    # dark. Fall back to the bg luminance if a custom theme sets neither.
    dark = theme.id != "light"
    return TextualTheme(
        name=f"pgntui-{theme.id}",
        primary=c["accent"],
        secondary=c.get("ok", c["accent"]),
        warning=c["warn"],
        error=c["alarm"],
        success=c["ok"],
        accent=c["accent"],
        foreground=c["fg"],
        background=c["bg"],
        surface=c["title_bg"],
        panel=c["title_bg"],
        dark=dark,
        variables={
            "border": c["border"],
            "footer-key-foreground": c["accent"],
        },
    )


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
    "list_builtin",
    "load_builtin",
    "load_theme",
    "to_textual_css",
    "to_textual_theme",
]
