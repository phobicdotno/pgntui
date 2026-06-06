"""Widgets must render theme colors, not plain monochrome strings.

The theme CSS classes (.state-ok, .bar-fill, ...) were generated but no
widget ever applied them — every signal row rendered in default fg/bg and
only the Header showed any theming. Widgets now receive the Theme and
render Rich text with the theme's colors and glyphs.
"""

from __future__ import annotations

from rich.text import Text

from pgntui.signals.base import AnalogIn, DigitalIn
from pgntui.signals.widgets import AnalogInWidget, DigitalInWidget
from pgntui.themes.loader import load_builtin

THEME = load_builtin("dark")


def _rpm(**kw) -> AnalogIn:
    return AnalogIn(
        id="rpm",
        type="analog_in",
        title="Engine RPM",
        pgn=127488,
        field="Engine Speed",
        unit="rpm",
        min=0,
        max=6000,
        decimals=0,
        **kw,
    )


def _styles(text: Text) -> set[str]:
    return {str(span.style) for span in text.spans}


def test_analog_render_uses_theme_colors() -> None:
    w = AnalogInWidget(_rpm(), theme=THEME)
    w.update_value(3000.0)
    out = w.render()
    assert isinstance(out, Text)
    styles = _styles(out)
    assert any(THEME.colors["bar_fill"] in s for s in styles), "marker not bar_fill colored"
    assert any(THEME.colors["bar_track"] in s for s in styles), "track not bar_track colored"
    assert any(THEME.colors["fg_dim"] in s for s in styles), "unit not fg_dim colored"


def test_analog_render_uses_state_color_for_value() -> None:
    w = AnalogInWidget(_rpm(warn_above=2000.0), theme=THEME)
    w.update_value(3000.0)
    out = w.render()
    assert isinstance(out, Text)
    assert any(THEME.colors["warn"] in s for s in _styles(out)), "warn value not warn colored"


def test_analog_render_uses_theme_glyphs() -> None:
    w = AnalogInWidget(_rpm(), theme=THEME)
    w.update_value(3000.0)
    plain = w.render().plain  # type: ignore[union-attr]
    assert THEME.glyphs["bar_left"] in plain
    assert THEME.glyphs["bar_marker"] in plain


def test_analog_render_without_theme_stays_plain() -> None:
    w = AnalogInWidget(_rpm())
    w.update_value(3000.0)
    assert w.render() == w.render_text()


def test_digital_render_uses_theme_colors() -> None:
    sig = DigitalIn(
        id="bilge",
        type="digital_in",
        title="Bilge Alarm",
        pgn=127501,
        field="Indicator1",
    )
    w = DigitalInWidget(sig, theme=THEME)
    w.update_value(True)
    out = w.render()
    assert isinstance(out, Text)
    assert any(THEME.colors["ok"] in s for s in _styles(out)), "ON glyph not ok colored"


def test_analog_render_diffuse_before_data() -> None:
    """A signal with no reading yet renders entirely in the dimmed look."""
    w = AnalogInWidget(_rpm(warn_above=2000.0), theme=THEME)
    assert not w.has_data
    styles = _styles(w.render())
    dim = THEME.colors["fg_dim"]
    assert all(dim in s for s in styles), f"not all diffuse: {styles}"
    # No live colors leak through before data arrives.
    assert not any(THEME.colors["bar_fill"] in s for s in styles)
    assert not any(THEME.colors["warn"] in s for s in styles)


def test_analog_brightens_after_data() -> None:
    w = AnalogInWidget(_rpm(), theme=THEME)
    w.update_value(3000.0)
    assert w.has_data
    assert any(THEME.colors["bar_fill"] in s for s in _styles(w.render())), "not live after data"


def test_analog_clear_returns_to_diffuse() -> None:
    w = AnalogInWidget(_rpm(), theme=THEME)
    w.update_value(3000.0)
    w.clear()
    assert not w.has_data
    assert all(THEME.colors["fg_dim"] in s for s in _styles(w.render()))


def test_digital_title_diffuse_before_data() -> None:
    sig = DigitalIn(
        id="bilge", type="digital_in", title="Bilge Alarm", pgn=127501, field="Indicator1"
    )
    w = DigitalInWidget(sig, theme=THEME)
    assert not w.has_data
    title_before = str(w.render().spans[0].style)  # type: ignore[union-attr]
    assert THEME.colors["fg_dim"] in title_before, f"title not diffuse: {title_before}"
    w.update_value(False)  # a real OFF reading
    title_after = str(w.render().spans[0].style)  # type: ignore[union-attr]
    assert THEME.colors["fg_dim"] not in title_after, f"still diffuse after data: {title_after}"
