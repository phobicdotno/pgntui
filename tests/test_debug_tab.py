from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import DecodedFrame


def _df(pgn: int, src: int, name: str = "X") -> DecodedFrame:
    return DecodedFrame(timestamp=1.0, source_addr=src, pgn=pgn, name=name, fields={"a": 1})


def test_buffer_appends_until_max() -> None:
    buf = DebugBuffer(max_rows=3)
    for i in range(5):
        buf.push(_df(pgn=100 + i, src=1))
    assert len(buf.rows()) == 3
    assert buf.rows()[0].pgn == 102


def test_pause_blocks_pushes() -> None:
    buf = DebugBuffer(max_rows=10)
    buf.push(_df(127488, 23))
    buf.paused = True
    buf.push(_df(130306, 35))
    assert len(buf.rows()) == 1


def test_filter_by_pgn() -> None:
    buf = DebugBuffer(max_rows=10, pgn_filter={127488})
    buf.push(_df(127488, 23))
    buf.push(_df(130306, 35))
    assert {r.pgn for r in buf.rows()} == {127488}


def test_filter_by_source() -> None:
    buf = DebugBuffer(max_rows=10, source_filter={23})
    buf.push(_df(127488, 23))
    buf.push(_df(127488, 99))
    assert all(r.source_addr == 23 for r in buf.rows())


def test_clear() -> None:
    buf = DebugBuffer(max_rows=10)
    buf.push(_df(1, 1))
    buf.clear()
    assert buf.rows() == []
