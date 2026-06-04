from pgntui import __version__


def test_version() -> None:
    assert __version__ == "0.1.2"


def test_main_returns_zero() -> None:
    from pgntui.__main__ import main

    assert main([]) == 0
