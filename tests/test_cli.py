from pathlib import Path

from pgntui.__main__ import main, parse_args


def test_parse_no_args() -> None:
    args = parse_args([])
    assert args.command is None
    assert args.workspace is None
    assert args.enable_write is False


def test_parse_replay_with_file() -> None:
    args = parse_args(["replay", "session.pgnlog"])
    assert args.command == "replay"
    assert args.replay_file == "session.pgnlog"


def test_parse_workspace_and_enable_write(tmp_path: Path) -> None:
    args = parse_args(["--workspace", str(tmp_path), "--enable-write"])
    assert args.workspace == str(tmp_path)
    assert args.enable_write is True


def test_parse_list_ports() -> None:
    assert parse_args(["--list-ports"]).list_ports is True
    assert parse_args([]).list_ports is False


def test_list_ports_runs_without_ui(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "pgntui.drivers.actisense.list_serial_ports",
        lambda: [("COM4", "USB Serial Port")],
    )
    rc = main(["--list-ports"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "COM4" in out
    assert "USB Serial Port" in out


def test_parse_probe() -> None:
    args = parse_args(["probe", "--port", "COM4", "--baud", "230400", "--seconds", "1.5"])
    assert args.command == "probe"
    assert args.port == "COM4"
    assert args.baud == 230400
    assert args.seconds == 1.5


def test_probe_reports_and_exit_code(tmp_path: Path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    from pgntui.drivers.actisense import ProbeResult

    captured: dict[str, object] = {}

    def fake_probe(port, baud=115200, duration=2.0, serial_factory=None):  # type: ignore[no-untyped-def]
        captured["port"] = port
        captured["baud"] = baud
        return ProbeResult(
            ok=True,
            port=port,
            baud=baud,
            bytes_read=200,
            frames=3,
            n2k_messages=3,
            sample_pgns=[127488],
        )

    monkeypatch.setattr("pgntui.drivers.actisense.probe_ngt1", fake_probe)
    rc = main(["--workspace", str(tmp_path), "probe", "--port", "COM9", "--baud", "115200"])
    assert rc == 0
    assert captured["port"] == "COM9"
    assert "Connected" in capsys.readouterr().out


def test_probe_without_port_errors(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    # Empty workspace -> default config has no driver.port.
    rc = main(["--workspace", str(tmp_path), "probe"])
    assert rc == 2
    assert "no port" in capsys.readouterr().err.lower()
