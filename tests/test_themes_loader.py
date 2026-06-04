import json
from pathlib import Path

import pytest

from pgntui.themes.loader import Theme, ThemeLoadError, load_builtin, load_theme, to_textual_css


def test_load_builtin_dark() -> None:
    theme = load_builtin("dark")
    assert isinstance(theme, Theme)
    assert theme.id == "dark"
    assert theme.colors["bg"].startswith("#")


def test_to_textual_css_contains_colors_and_classes() -> None:
    theme = load_builtin("dark")
    css = to_textual_css(theme)
    assert theme.colors["bg"] in css
    assert ".bar-fill" in css
    assert ".bar-warn" in css
    assert ".bar-alarm" in css
    assert ".signal-title" in css


def test_load_theme_from_path(tmp_path: Path) -> None:
    dark = Path(__file__).resolve().parent.parent / "src/pgntui/themes/builtin/dark.json"
    payload = json.loads(dark.read_text(encoding="utf-8"))
    payload["id"] = "custom"
    payload["title"] = "Custom"
    p = tmp_path / "custom.json"
    p.write_text(json.dumps(payload))
    theme = load_theme(p)
    assert theme.id == "custom"


def test_missing_required_color_fails(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"id": "bad", "title": "Bad", "colors": {"bg": "#000"}}))
    with pytest.raises(ThemeLoadError):
        load_theme(p)


def test_gradients_block_round_trips(tmp_path: Path) -> None:
    payload = {
        "id": "rainbow",
        "title": "R",
        "colors": {
            k: "#000000"
            for k in (
                "bg fg fg_dim accent ok warn alarm border title_bg title_fg "
                "bar_track bar_fill bar_warn bar_alarm"
            ).split()
        },
        "glyphs": {
            "bar_left": "|",
            "bar_right": "|",
            "bar_track": "-",
            "bar_marker": "*",
            "on": "*",
            "off": "o",
            "box": "ascii",
        },
        "styles": {},
        "gradients": [{"target": "bar_fill", "stops": ["#ff0000", "#00ff00", "#0000ff"]}],
        "animate": True,
        "animate_fps": 6,
    }
    p = tmp_path / "rainbow.json"
    p.write_text(json.dumps(payload))
    theme = load_theme(p)
    assert theme.animate is True
    assert theme.animate_fps == 6
    assert theme.gradients[0].target == "bar_fill"
    assert theme.gradients[0].stops == ("#ff0000", "#00ff00", "#0000ff")
