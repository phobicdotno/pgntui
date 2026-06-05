"""Validate the shipped JSON library (library/<page>/{signals,containers}).

Every page must load through the real loaders, every container ref must
resolve, and every signal must bind to a PGN + field name that the bundled
canboat database can actually decode (raw canboat name or registered alias).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pgntui.containers.loader import load_container
from pgntui.decode.canboat import _FIELD_ALIASES, CanboatDecoder
from pgntui.signals.base import DigitalIn, load_signals_dir

LIBRARY = Path(__file__).parent.parent / "library"

PAGES = sorted(p.name for p in LIBRARY.iterdir() if p.is_dir())


def _decodable_field_names(db: dict, pgn: int) -> set[str]:
    names: set[str] = set()
    for entry in db["PGNs"]:
        if entry.get("PGN") == pgn:
            for f in entry.get("Fields", []):
                name = f.get("Name")
                if name:
                    names.add(name)
                    alias = _FIELD_ALIASES.get((pgn, name))
                    if alias:
                        names.add(alias)
            break
    return names


@pytest.fixture(scope="module")
def bundled_db() -> dict:
    import importlib.resources as resources

    with resources.files("pgntui.decode").joinpath("pgns.json").open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_library_has_pages() -> None:
    assert len(PAGES) >= 13


@pytest.mark.parametrize("page", PAGES)
def test_page_signals_load_and_containers_resolve(page: str) -> None:
    sig_dir = LIBRARY / page / "signals"
    c_dir = LIBRARY / page / "containers"
    signals = load_signals_dir(sig_dir)
    assert signals, f"{page}: no signals"
    ids = {s.id for s in signals}
    assert len(ids) == len(signals), f"{page}: duplicate signal ids"
    containers = sorted(c_dir.glob("*.json"))
    assert containers, f"{page}: no containers"
    for path in containers:
        container = load_container(path, ids)
        refs = {p.ref for p in container.signals}
        assert refs == ids, f"{page}: container does not place every signal"


@pytest.mark.parametrize("page", PAGES)
def test_page_fields_decodable_by_bundled_db(page: str, bundled_db: dict) -> None:
    decoder = CanboatDecoder(bundled_db)
    for sig in load_signals_dir(LIBRARY / page / "signals"):
        assert decoder.has_pgn(sig.pgn), f"{page}/{sig.id}: PGN {sig.pgn} not in bundled db"
        names = _decodable_field_names(bundled_db, sig.pgn)
        assert sig.field in names, (
            f"{page}/{sig.id}: field {sig.field!r} not decodable for PGN {sig.pgn}"
        )


@pytest.mark.parametrize("page", PAGES)
def test_bit_signals_fit_field_width(page: str, bundled_db: dict) -> None:
    """A digital_in ``bit`` index must fall inside the bound field's width."""
    for sig in load_signals_dir(LIBRARY / page / "signals"):
        if not isinstance(sig, DigitalIn) or sig.bit is None:
            continue
        for entry in bundled_db["PGNs"]:
            if entry.get("PGN") == sig.pgn:
                widths = {
                    f.get("Name"): int(f.get("BitLength") or 0) for f in entry.get("Fields", [])
                }
                width = widths.get(sig.field, 0)
                assert 0 <= sig.bit < width, (
                    f"{page}/{sig.id}: bit {sig.bit} outside {sig.field!r} ({width} bits)"
                )
                break
