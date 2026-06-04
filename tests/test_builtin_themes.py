import pytest

from pgntui.themes.loader import load_builtin, to_textual_css

BUILTINS = ["dark", "light", "amber-crt", "green-phosphor", "mono-ascii", "rainbow-disco"]


@pytest.mark.parametrize("name", BUILTINS)
def test_each_builtin_loads(name: str) -> None:
    theme = load_builtin(name)
    assert theme.id == name


@pytest.mark.parametrize("name", BUILTINS)
def test_each_builtin_renders_css(name: str) -> None:
    theme = load_builtin(name)
    css = to_textual_css(theme)
    assert "Screen {" in css
    assert ".bar-fill" in css


def test_rainbow_has_gradient_and_animate() -> None:
    theme = load_builtin("rainbow-disco")
    assert theme.gradients
    assert theme.animate is True


def test_mono_ascii_uses_ascii_glyphs() -> None:
    theme = load_builtin("mono-ascii")
    assert theme.glyphs["box"] == "ascii"
