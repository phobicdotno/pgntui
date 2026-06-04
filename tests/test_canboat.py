from pgntui.decode.canboat import CanboatDecoder, DecodedFrame
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
    from pgntui.drivers.base import Frame

    dec = CanboatDecoder.load_bundled()
    bogus = Frame(timestamp=0.0, source_addr=0, pgn=999999, data=b"\x00")
    assert dec.decode(bogus) is None
