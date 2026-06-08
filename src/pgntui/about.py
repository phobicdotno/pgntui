"""App identity and a short, curated changelog for the About screen.

Pure data + string helpers — no Textual import — so it ships as plain package
data and can be unit-tested in isolation. The full history lives in
``CHANGELOG.md``; this is the trimmed, one-line-per-release highlight reel.
"""

from __future__ import annotations

from pgntui import __version__

APP_NAME = "PgnTui"
TAGLINE = "NMEA 2000 reader"
COPYRIGHT = "© 2026 Karstein Kvistad (phobicdotno)"

# Curated highlights, newest first — keep each to one short line.
# The top entry's version MUST equal ``__version__`` (enforced by a test) so the
# About screen can never silently lag a release.
RELEASE_NOTES: tuple[tuple[str, str], ...] = (
    ("0.6.17", "Quit now closes the driver: fast exit and the serial port is freed."),
    ("0.6.16", "Remember the last column layout (1/2/3, Shift, F-keys) across runs."),
    ("0.6.15", "Fix Debug freeze: capped scrollback; views fed only when open."),
    ("0.6.14", "Auto: one box per Instance (title '· Instance X'); F1/F2/F3 here."),
    ("0.6.13", "Each engine instance gets its own labelled section (no jumping)."),
    ("0.6.12", "Title bar + About show © 2026 Karstein Kvistad (phobicdotno)."),
    ("0.6.11", "Fix: NGT-1 fast-packet PGNs (engine dynamic, GPS) were dropped."),
    ("0.6.10", "Readable footer; double-border sections; clickable instance bar."),
    ("0.6.9", "Page columns are F1/F2/F3 (Ctrl+digit isn't sent by all terminals)."),
    ("0.6.8", "Ctrl+1/2/3 lays the pages out in 1/2/3 columns; sections get boxes."),
    ("0.6.7", "Nav/Engine/Main now share one Main tab as labelled sections."),
    ("0.6.6", "Group-column hint now reads 'Shift+' instead of the terse 'G:'."),
    ("0.6.5", "Shift+1/2/3 sets 1/2/3 group-box columns; signals auto-fit."),
    ("0.6.4", "Key 3 adds three equal columns, offered only on wide terminals."),
    ("0.6.3", "Bars all end at the same column (fixed value area); values align."),
    ("0.6.2", "Analog bars fill the row width (full-width in one-column mode)."),
    ("0.6.1", "Live theme switch now re-themes the Auto page rows too."),
    ("0.6.0", "Auto tab: a live, auto-built view of every PGN/source on the bus."),
    ("0.5.1", "Key 2 lays out two equal 50% columns; key 1 stays one column."),
    ("0.5.0", "Toggle one-column vs multi-column layout (keys 1 and 2)."),
    ("0.4.3", "Keep full signal titles next to the [+] toggle (no truncation)."),
    ("0.4.2", "Every signal shows a clickable [+] to reveal its sparkline."),
    ("0.4.1", "Fix multi-column row spacing; sparklines show in narrow cells."),
    ("0.4.0", "Sparklines: press + (or click) a signal for its history."),
    ("0.3.13", "Signals stay dimmed until they report (no-data look)."),
    ("0.3.12", "Switch engine instance with [ and ] (Stb/Port/gens)."),
    ("0.3.11", "Wider About dialog with aligned, one-line entries."),
    ("0.3.10", "Fixed Connect crash and a stray driver warning."),
    ("0.3.9", "Connection menu: port, speed, test, connect."),
    ("0.3.8", "About dialog and a titled header with version."),
    ("0.3.7", "Real Actisense NGT-1 serial driver; --list-ports."),
    ("0.3.6", "Themed chrome, compact rows, full signal library."),
    ("0.3.5", "Signal widgets use the theme's colors."),
    ("0.3.4", "Display-unit scaling, status lamps, Nav/Engine tabs."),
    ("0.3.3", "Fixed blank dashboard tabs."),
)


def header_title() -> str:
    """The top-bar string, e.g.
    ``PgnTui — NMEA 2000 reader — v0.3.8 — © 2026 Karstein Kvistad``."""
    return f"{APP_NAME} — {TAGLINE} — v{__version__} — {COPYRIGHT}"


def changelog_lines(limit: int = 6) -> list[str]:
    """Return up to ``limit`` ``vX.Y.Z  summary`` lines, newest first.

    The version is padded to a fixed width so every summary starts at the same
    column (lines up under each other) regardless of version-string length.
    """
    width = max(len(ver) for ver, _ in RELEASE_NOTES[:limit])
    return [f"v{ver:<{width}}  {summary}" for ver, summary in RELEASE_NOTES[:limit]]


__all__ = ["APP_NAME", "COPYRIGHT", "RELEASE_NOTES", "TAGLINE", "changelog_lines", "header_title"]
