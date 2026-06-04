"""Ship-time check: every signal JSON in the bundled example workspace loads."""

from __future__ import annotations

from importlib import resources

import pytest

from pgntui.signals.base import AnalogIn, AnalogOut, DigitalIn, DigitalOut, load_signal


@pytest.mark.parametrize(
    "name",
    ["engine_rpm", "speed", "depth", "water_temp"],
)
def test_each_example_signal_loads(name: str, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Every bundled signal JSON parses into a real Signal subclass."""
    src = resources.files("pgntui.examples.signals").joinpath(f"{name}.json")
    target = tmp_path / f"{name}.json"
    with src.open("rb") as fh:
        target.write_bytes(fh.read())
    sig = load_signal(target)
    # The 4 bundled signals are all analog_in dashboards. If we ever ship a
    # digital example, extend this assertion.
    assert isinstance(sig, AnalogIn)
    assert sig.id == name
    assert sig.pgn > 0
    assert sig.field
    assert sig.min < sig.max
    assert sig.smoothing >= 0


def test_signal_load_round_trip_all_types(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Cover analog_in, analog_out, digital_in, digital_out signal types."""
    samples: list[tuple[str, type]] = [
        (
            '{"id":"x","type":"analog_in","title":"X","pgn":1,"field":"f","min":0,"max":1}',
            AnalogIn,
        ),
        (
            '{"id":"y","type":"analog_out","title":"Y","pgn":2,"field":"f",'
            '"min":0,"max":1,"write_pgn":2,"write_field":"f"}',
            AnalogOut,
        ),
        ('{"id":"z","type":"digital_in","title":"Z","pgn":3,"field":"g"}', DigitalIn),
        (
            '{"id":"w","type":"digital_out","title":"W","pgn":4,"field":"g",'
            '"write_pgn":4,"write_field":"g"}',
            DigitalOut,
        ),
    ]
    for i, (body, klass) in enumerate(samples):
        p = tmp_path / f"s{i}.json"
        p.write_text(body)
        sig = load_signal(p)
        assert isinstance(sig, klass)
