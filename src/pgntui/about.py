"""App identity and a short, curated changelog for the About screen.

Pure data + string helpers — no Textual import — so it ships as plain package
data and can be unit-tested in isolation. The full history lives in
``CHANGELOG.md``; this is the trimmed, one-line-per-release highlight reel.
"""

from __future__ import annotations

from pgntui import __version__

APP_NAME = "PgnTui"
TAGLINE = "NMEA 2000 reader"

# Curated highlights, newest first — keep each to one short line.
# The top entry's version MUST equal ``__version__`` (enforced by a test) so the
# About screen can never silently lag a release.
RELEASE_NOTES: tuple[tuple[str, str], ...] = (
    ("0.3.10", "Fixed a crash when pressing Connect, and a stray driver warning."),
    ("0.3.9", "Connection menu: pick port + speed, test the NGT-1, save/connect."),
    ("0.3.8", "About screen and a titled header showing the version."),
    ("0.3.7", "Actisense NGT-1 serial driver (real BST protocol); --list-ports."),
    ("0.3.6", "Themed header & tabs, compact grouped rows, full signal library."),
    ("0.3.5", "Signal widgets render the theme's colors."),
    ("0.3.4", "Display-unit scaling, status lamps, Nav/Engine example tabs."),
    ("0.3.3", "Fixed blank dashboard tabs."),
)


def header_title() -> str:
    """The string shown in the top bar, e.g. ``PgnTui — NMEA 2000 reader — v0.3.8``."""
    return f"{APP_NAME} — {TAGLINE} — v{__version__}"


def changelog_lines(limit: int = 6) -> list[str]:
    """Return up to ``limit`` ``vX.Y.Z  summary`` lines, newest first."""
    return [f"v{ver}  {summary}" for ver, summary in RELEASE_NOTES[:limit]]


__all__ = ["APP_NAME", "RELEASE_NOTES", "TAGLINE", "changelog_lines", "header_title"]
