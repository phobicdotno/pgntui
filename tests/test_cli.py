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
