from datetime import datetime, timezone
from pathlib import Path

from pgntui.logging.csv import CSVSignalLogger


def test_appends_timestamp_value(tmp_path: Path) -> None:
    log = CSVSignalLogger(base_dir=tmp_path)
    log.log("engine_rpm", timestamp=datetime(2026, 6, 4, 12, tzinfo=timezone.utc).timestamp(), value=2150.0)
    log.log("engine_rpm", timestamp=datetime(2026, 6, 4, 12, 0, 1, tzinfo=timezone.utc).timestamp(), value=2160.0)
    log.close()
    f = tmp_path / "engine_rpm-2026-06-04.csv"
    assert f.exists()
    lines = f.read_text().strip().splitlines()
    assert len(lines) == 2
    assert lines[0].endswith("2150.0")


def test_rotates_at_day_boundary(tmp_path: Path) -> None:
    log = CSVSignalLogger(base_dir=tmp_path)
    day1 = datetime(2026, 6, 4, 23, 59, 59, tzinfo=timezone.utc).timestamp()
    day2 = datetime(2026, 6, 5, 0, 0, 1, tzinfo=timezone.utc).timestamp()
    log.log("x", day1, 1.0)
    log.log("x", day2, 2.0)
    log.close()
    assert (tmp_path / "x-2026-06-04.csv").exists()
    assert (tmp_path / "x-2026-06-05.csv").exists()
