from pathlib import Path

from pgntui.__main__ import parse_args


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
