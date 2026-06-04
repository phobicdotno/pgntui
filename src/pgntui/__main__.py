"""CLI entry point for pgntui."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pgntui.config import load_config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pgntui", description="NMEA 2000 terminal UI")
    p.add_argument("--workspace", default=None, help="override workspace directory")
    p.add_argument("--enable-write", action="store_true", help="enable writes")
    sub = p.add_subparsers(dest="command")
    replay = sub.add_parser("replay", help="replay a .pgnlog file")
    replay.add_argument("replay_file")
    return p


def parse_args(argv: list[str]) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    workspace = (
        Path(args.workspace).expanduser()
        if args.workspace
        else Path("~/.config/pgntui").expanduser()
    )
    cfg_path = workspace / "config.toml"
    cfg = load_config(cfg_path)
    if args.enable_write:
        # Re-create with write_enabled flipped on
        cfg = type(cfg)(
            driver_name=cfg.driver_name,
            driver_options=cfg.driver_options,
            write_enabled=True,
            theme=cfg.theme,
            workspace=workspace,
            csv_dir=cfg.csv_dir,
            record_dir=cfg.record_dir,
        )
    if args.command == "replay":
        # Replay mode is bootstrapped here in a later integration step.
        print(f"replay: {args.replay_file} (workspace={workspace}, theme={cfg.theme})")
        return 0
    print(f"pgntui: workspace={workspace} theme={cfg.theme} write_enabled={cfg.write_enabled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
