from pgntui.decode.canboat import CanboatDecoder, DecodedFrame
from pgntui.drivers.base import Frame
from tests.fixtures.frames import ENGINE_RAPID


def test_decoder_loads_bundled_pgns() -> None:
    dec = CanboatDecoder.load_bundled()
    assert dec.has_pgn(127488)


def test_decode_engine_rapid_rpm_units() -> None:
    dec = CanboatDecoder.load_bundled()
    result = dec.decode(ENGINE_RAPID)
    assert isinstance(result, DecodedFrame)
    assert result.pgn == 127488
    assert result.name and "Engine" in result.name
    rpm = result.fields.get("Engine Speed")
    assert rpm is not None
    assert 2140 <= float(rpm) <= 2160


def test_decode_unknown_pgn_returns_none() -> None:
    dec = CanboatDecoder.load_bundled()
    bogus = Frame(timestamp=0.0, source_addr=0, pgn=999999, data=b"\x00")
    assert dec.decode(bogus) is None


def test_decode_applies_offset_for_ac_power() -> None:
    """PGN 65007 Real/Apparent Power have Offset -2000000000.

    Without the offset, frames decode 2 GW too high. We craft raw 32-bit
    values just above the offset magnitude so the post-offset reading is a
    small positive number of watts.
    """
    dec = CanboatDecoder.load_bundled()
    # Real Power: raw 2_000_000_001 -> 0x77359401 -> 1.0 W after offset.
    # Apparent Power: raw 2_000_000_005 -> 0x77359405 -> 5.0 VA after offset.
    # Both fields are 32-bit signed; the raw values are below 2^31 so the
    # sign-extension branch is not triggered.
    payload = bytes(
        [0x01, 0x94, 0x35, 0x77]  # Real Power LE
        + [0x05, 0x94, 0x35, 0x77]  # Apparent Power LE
    )
    frame = Frame(timestamp=0.0, source_addr=0, pgn=65007, data=payload)
    decoded = dec.decode(frame)
    assert decoded is not None
    real = decoded.fields.get("Real Power")
    apparent = decoded.fields.get("Apparent Power")
    assert real is not None and apparent is not None
    assert float(real) == 1.0
    assert float(apparent) == 5.0
