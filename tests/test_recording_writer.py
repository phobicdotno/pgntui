from pathlib import Path

from pgntui.drivers.base import Frame
from pgntui.recording.writer import ActisenseLogWriter


def test_writes_actisense_log_line(tmp_path: Path) -> None:
    path = tmp_path / "rec.pgnlog"
    writer = ActisenseLogWriter(path)
    writer.open()
    writer.write(Frame(timestamp=1717000000.0, source_addr=23, pgn=127488, data=bytes(range(8))))
    writer.close()
    content = path.read_text().strip().split(",")
    assert content[2] == "127488"
    assert content[3] == "23"
    assert content[5] == "8"
    assert content[6:14] == ["00", "01", "02", "03", "04", "05", "06", "07"]
    assert writer.frame_count == 1


def test_tracks_size_and_count(tmp_path: Path) -> None:
    path = tmp_path / "rec.pgnlog"
    w = ActisenseLogWriter(path)
    w.open()
    for i in range(5):
        w.write(Frame(timestamp=1.0 + i, source_addr=1, pgn=1, data=b"\x00"))
    w.close()
    assert w.frame_count == 5
    assert w.bytes_written > 0
