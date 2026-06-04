from pathlib import Path

from pgntui.containers.loader import load_container
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalKey, SignalRouter
from pgntui.drivers.replay import FileReplayDriver
from pgntui.logging.csv import CSVSignalLogger
from pgntui.signals.base import AnalogIn, load_signals_dir

FX = Path(__file__).parent / "fixtures"


def test_e2e_replay_drives_signals_and_csv(tmp_path: Path) -> None:
    signals = {s.id: s for s in load_signals_dir(FX / "e2e_signals")}
    assert set(signals) == {"engine_rpm", "wind_speed"}
    containers = [
        load_container(FX / "e2e_containers" / "engine.json", set(signals)),
        load_container(FX / "e2e_containers" / "nav.json", set(signals)),
    ]
    assert {c.id for c in containers} == {"engine", "nav"}

    decoder = CanboatDecoder.load_bundled()
    router = SignalRouter()
    for sid, sig in signals.items():
        router.bind(sid, SignalKey(pgn=sig.pgn, field=sig.field, source=sig.source))

    driver = FileReplayDriver()
    driver.open({"path": str(FX / "e2e_session.pgnlog"), "speed": "max"})

    csv_logger = CSVSignalLogger(base_dir=tmp_path)
    last: dict[str, float] = {}

    for frame in driver.read_frames():
        decoded = decoder.decode(frame)
        if decoded is None:
            continue
        for update in router.route(decoded):
            last[update.signal_id] = float(update.value)
            sig = signals[update.signal_id]
            if sig.log and isinstance(sig, AnalogIn):
                csv_logger.log(update.signal_id, update.timestamp, float(update.value))

    driver.close()
    csv_logger.close()

    assert "engine_rpm" in last
    assert 2140 <= last["engine_rpm"] <= 2160
    assert "wind_speed" in last

    logs = list(tmp_path.glob("engine_rpm-*.csv"))
    assert logs, "expected engine_rpm CSV"
    assert len(logs[0].read_text().strip().splitlines()) == 3
