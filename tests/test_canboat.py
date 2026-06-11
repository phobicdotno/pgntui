import struct

import pytest

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


def _heading_127250(variation_raw: int, reference: int = 0) -> Frame:
    # PGN 127250 Vessel Heading: SID(8) Heading(16,u) Deviation(16,s)
    # Variation(16,s) Reference(2 bits, LOOKUP) + Reserved. Heading 1.0 rad.
    return Frame(
        timestamp=0.0,
        source_addr=100,
        pgn=127250,
        data=bytes([0xFF, 0x10, 0x27, 0x00, 0x00])
        + struct.pack("<H", variation_raw)
        + bytes([reference & 0x03]),
    )


def test_decode_resolves_lookup_field_to_label() -> None:
    dec = CanboatDecoder.load_bundled()
    # DIRECTION_REFERENCE: 0 -> True, 1 -> Magnetic.
    assert dec.decode(_heading_127250(1000, reference=1)).fields["Reference"] == "Magnetic"
    assert dec.decode(_heading_127250(1000, reference=0)).fields["Reference"] == "True"


def test_decode_keeps_instance_lookup_numeric() -> None:
    # PGN 127488's Instance is an ENGINE_INSTANCE lookup, but it keys the
    # instance-switchable containers and routing, which compare against an int —
    # so it must stay numeric, not resolve to a label string.
    dec = CanboatDecoder.load_bundled()
    raw = round(1778 / 0.25)
    data = bytes([0, raw & 0xFF, (raw >> 8) & 0xFF, 0xFF, 0xFF, 0x7F])
    result = dec.decode(Frame(timestamp=0.0, source_addr=0, pgn=127488, data=data))
    assert result is not None
    assert result.fields["Instance"] == 0
    assert isinstance(result.fields["Instance"], int)


def test_field_unit_returns_canboat_si_unit() -> None:
    dec = CanboatDecoder.load_bundled()
    assert dec.field_unit(127250, "Heading") == "rad"
    assert dec.field_unit(127250, "Nonexistent") is None


def test_decode_skips_reserved_fields() -> None:
    dec = CanboatDecoder.load_bundled()
    result = dec.decode(_heading_127250(1000))
    assert result is not None
    assert not any("reserved" in name.lower() for name in result.fields)


def test_decode_drops_not_available_variation_sentinel() -> None:
    # 0x7FFF is the reserved "not available" value for a signed 16-bit field; it
    # must NOT decode to a bogus 187.7 deg reading. The field is dropped so the
    # router skips it and the gauge keeps its last good value (no flicker).
    dec = CanboatDecoder.load_bundled()
    result = dec.decode(_heading_127250(0x7FFF))
    assert result is not None
    assert "Variation" not in result.fields  # sentinel dropped
    assert "Heading" in result.fields  # valid field still decoded


def test_decode_keeps_valid_variation() -> None:
    dec = CanboatDecoder.load_bundled()
    result = dec.decode(_heading_127250(1000))  # 0.1 rad
    assert result is not None
    assert result.fields.get("Variation") == pytest.approx(0.1, abs=1e-3)


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


def _fp_frame(seq: int, idx: int, chunk: bytes, *, source: int, pgn: int) -> Frame:
    """Wrap a fast-packet CAN frame into a :class:`Frame` instance."""
    header = ((seq & 0x07) << 5) | (idx & 0x1F)
    return Frame(timestamp=1700000000.0, source_addr=source, pgn=pgn, data=bytes([header]) + chunk)


def test_decoder_fast_packet_assembly_completes() -> None:
    """Feed multi-frame PGN 129029 (GNSS Position Data) through ``decode``.

    PGN 129029 has ``Type: Fast`` and ``MinLength: 43`` in the bundled
    canboat database. With 6 useful bytes in frame 0 and 7 in each
    continuation, 7 frames (0..6) carry 6 + 6*7 = 48 bytes — more than
    enough for the 43-byte minimum payload.

    We construct a payload where the first three fields (SID, Date, Time)
    decode to known values, then assert the decoder produces them.
    """
    dec = CanboatDecoder.load_bundled()
    assert dec.has_pgn(129029)

    # Build a 43-byte payload:
    #   byte  0     : SID = 0x42
    #   bytes 1-2   : Date (uint16 LE) = 12345
    #   bytes 3-6   : Time (uint32 LE) = 50_000_000 (raw; resolution 0.0001)
    #   bytes 7-42  : padded zeros (lat/lon/alt left at 0 for simplicity)
    sid = bytes([0x42])
    date = struct.pack("<H", 12345)
    time_raw = struct.pack("<I", 50_000_000)
    payload = sid + date + time_raw + b"\x00" * (43 - 7)
    assert len(payload) == 43

    # Length byte for frame 0 declares the total payload length.
    length = len(payload)
    # Frame 0 carries [header][length][payload[0:6]] -> 6 useful bytes.
    f0 = Frame(
        timestamp=1700000000.0,
        source_addr=15,
        pgn=129029,
        data=bytes([((1 & 0x07) << 5) | 0x00, length]) + payload[0:6],
    )
    # Continuation frames each carry 7 useful payload bytes.
    chunks = [payload[6 + i * 7 : 6 + (i + 1) * 7] for i in range(6)]
    # Pad the final chunk to 7 bytes if it's shorter (real CAN frames are 8 bytes).
    chunks[-1] = chunks[-1] + b"\x00" * (7 - len(chunks[-1]))
    continuation_frames = [
        _fp_frame(seq=1, idx=i + 1, chunk=chunk, source=15, pgn=129029)
        for i, chunk in enumerate(chunks)
    ]

    # First frame: nothing decoded yet.
    assert dec.decode(f0) is None
    # Continuation frames 1..5 return None too.
    for cf in continuation_frames[:-1]:
        assert dec.decode(cf) is None
    # Final continuation completes the message.
    result = dec.decode(continuation_frames[-1])
    assert isinstance(result, DecodedFrame)
    assert result.pgn == 129029
    assert result.name and "GNSS" in result.name
    assert result.fields.get("SID") == 0x42
    assert result.fields.get("Date") == 12345
    # Time is resolution=0.0001; 50_000_000 * 0.0001 == 5000.0 seconds.
    time_val = result.fields.get("Time")
    assert time_val is not None
    assert abs(float(time_val) - 5000.0) < 1e-6


def test_decoder_single_frame_unaffected_by_reassembler() -> None:
    """Single-frame PGNs must continue to decode on a single ``decode`` call."""
    dec = CanboatDecoder.load_bundled()
    # Same fixture frame as the existing happy-path test, but explicit so we
    # know the reassembler did NOT swallow it.
    result = dec.decode(ENGINE_RAPID)
    assert isinstance(result, DecodedFrame)
    assert result.pgn == 127488
