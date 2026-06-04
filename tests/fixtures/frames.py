"""Hand-built raw NMEA 2000 frames used in unit tests."""

from pgntui.drivers.base import Frame

# PGN 127488 Engine Parameters Rapid Update
# Byte layout per canboat:
#   0: instance (uint8)         = 0
#   1-2: engine speed (uint16 LE, resolution 0.25 rpm) = 2150 rpm -> 8600 -> 0x2198
#   3-4: boost pressure (uint16 LE, resolution 100 Pa) = 1200 Pa -> 12 -> 0x000C
#   5: tilt/trim (int8)         = 0
#   6-7: reserved               = 0xFFFF
ENGINE_RAPID = Frame(
    timestamp=1700000000.0,
    source_addr=23,
    pgn=127488,
    data=bytes([0x00, 0x98, 0x21, 0x0C, 0x00, 0x00, 0xFF, 0xFF]),
)
