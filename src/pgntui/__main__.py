"""CLI entry point for pgntui."""

from __future__ import annotations

import argparse
import shutil
import sys
from importlib import resources
from importlib.metadata import entry_points
from pathlib import Path

from pgntui.app import PgntuiApp
from pgntui.config import Config, _default_workspace, load_config
from pgntui.containers.loader import Container, load_container
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalKey, SignalRouter
from pgntui.drivers.base import Driver
from pgntui.drivers.replay import FileReplayDriver
from pgntui.signals.base import Signal, load_signals_dir
from pgntui.themes.loader import ThemeLoadError, load_builtin


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pgntui", description="NMEA 2000 terminal UI")
    p.add_argument("--workspace", default=None, help="override workspace directory")
    p.add_argument("--enable-write", action="store_true", help="enable writes")
    p.add_argument("--check", action="store_true", help="print config and exit (no UI)")
    p.add_argument(
        "--example",
        action="store_true",
        help="scaffold an example workspace at --workspace (or the OS default location) and exit",
    )
    sub = p.add_subparsers(dest="command")
    replay = sub.add_parser("replay", help="replay a .pgnlog file")
    replay.add_argument("replay_file")
    return p


def parse_args(argv: list[str]) -> argparse.Namespace:
    return build_parser().parse_args(argv)


# ---------------------------------------------------------------------------
# Workspace helpers
# ---------------------------------------------------------------------------


def resolve_workspace(arg: str | None) -> Path:
    return (Path(arg).expanduser() if arg else _default_workspace()).resolve()


def scaffold_example(workspace: Path) -> int:
    """Copy the bundled example workspace into ``workspace``.

    Refuses to clobber an existing directory — the user must point at a fresh
    path or delete the old one.
    """
    if workspace.exists() and any(workspace.iterdir()):
        print(
            f"workspace exists at {workspace}, refusing to overwrite. "
            "Pass --workspace <other> or delete the directory.",
            file=sys.stderr,
        )
        return 2
    workspace.mkdir(parents=True, exist_ok=True)
    src_root = resources.files("pgntui.examples")
    _copy_resource_tree(src_root, workspace)
    print(f"scaffolded example workspace at {workspace}")
    return 0


def _copy_resource_tree(src: object, dst: Path) -> None:
    """Recursively copy a ``importlib.resources`` Traversable into ``dst``.

    Plain ``shutil.copytree`` doesn't work because the source may be inside a
    zipped wheel. We re-implement a minimal recursive copy that uses the
    Traversable API.
    """
    for entry in src.iterdir():  # type: ignore[attr-defined]
        name = entry.name
        if name in ("__init__.py", "__pycache__"):
            continue
        target = dst / name
        if entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            _copy_resource_tree(entry, target)
        else:
            with entry.open("rb") as src_fh, target.open("wb") as dst_fh:
                shutil.copyfileobj(src_fh, dst_fh)


# ---------------------------------------------------------------------------
# Signal / container discovery
# ---------------------------------------------------------------------------


def discover_signals(workspace: Path) -> dict[str, Signal]:
    sig_dir = workspace / "signals"
    if not sig_dir.is_dir():
        return {}
    return {s.id: s for s in load_signals_dir(sig_dir)}


def discover_containers(workspace: Path, signal_ids: set[str]) -> list[Container]:
    c_dir = workspace / "containers"
    if not c_dir.is_dir():
        return []
    out: list[Container] = []
    for p in sorted(c_dir.glob("*.json")):
        out.append(load_container(p, signal_ids))
    return out


def make_router(signals: dict[str, Signal]) -> SignalRouter:
    router = SignalRouter()
    for sid, sig in signals.items():
        router.bind(
            sid,
            SignalKey(pgn=sig.pgn, field=sig.field, source=sig.source, instance=sig.instance),
        )
    return router


# ---------------------------------------------------------------------------
# Driver instantiation
# ---------------------------------------------------------------------------


def load_driver(name: str) -> Driver | None:
    """Look up a driver factory by entry-point name.

    Returns ``None`` if the entry point is missing — useful when the user runs
    pgntui without a real device. The caller decides whether to fall back to a
    no-driver UI or replace with a file-replay driver.
    """
    try:
        eps = entry_points(group="pgntui.drivers")
    except TypeError:  # pragma: no cover — very old importlib.metadata fallback
        return None
    for ep in eps:
        if ep.name == name:
            factory = ep.load()
            instance = factory()
            # Runtime check that the factory produced a Driver-shaped object.
            return instance  # type: ignore[no-any-return]
    return None


def open_driver_or_none(driver: Driver | None, options: dict[str, object]) -> Driver | None:
    """Open the driver, swallowing errors so a missing serial device etc.
    degrades gracefully into a no-driver UI."""
    if driver is None:
        return None
    try:
        driver.open(options)
    except Exception as e:
        print(f"warning: failed to open driver: {e}", file=sys.stderr)
        return None
    return driver


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _apply_enable_write(cfg: Config, workspace: Path) -> Config:
    return Config(
        driver_name=cfg.driver_name,
        driver_options=cfg.driver_options,
        write_enabled=True,
        theme=cfg.theme,
        workspace=workspace,
        csv_dir=cfg.csv_dir,
        record_dir=cfg.record_dir,
    )


def _build_app(
    cfg: Config,
    workspace: Path,
    driver: Driver | None,
) -> PgntuiApp:
    try:
        theme = load_builtin(cfg.theme)
    except ThemeLoadError:
        theme = load_builtin("dark")
    signals = discover_signals(workspace)
    containers = discover_containers(workspace, set(signals))
    decoder = CanboatDecoder.load_bundled()
    router = make_router(signals)
    debug_buffer = DebugBuffer()
    record_dir = (workspace / cfg.record_dir).resolve()
    return PgntuiApp(
        theme=theme,
        driver=driver,
        decoder=decoder,
        router=router,
        signals=signals,
        containers=containers,
        write_enabled=cfg.write_enabled,
        record_dir=record_dir,
        debug_buffer=debug_buffer,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    workspace = resolve_workspace(args.workspace)

    if args.example:
        return scaffold_example(workspace)

    cfg_path = workspace / "config.toml"
    try:
        cfg = load_config(cfg_path)
    except ValueError as e:
        # ``load_config`` wraps TOML decode errors in ValueError carrying the
        # file path + line/column. Print friendly and exit non-zero rather than
        # dumping a raw traceback on the user.
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.enable_write:
        cfg = _apply_enable_write(cfg, workspace)

    if args.check:
        print(f"pgntui: workspace={workspace} theme={cfg.theme} write_enabled={cfg.write_enabled}")
        return 0

    if args.command == "replay":
        replay_path = Path(args.replay_file).expanduser().resolve()
        if not replay_path.exists():
            print(f"replay file not found: {replay_path}", file=sys.stderr)
            return 2
        driver: Driver | None = FileReplayDriver()
        driver = open_driver_or_none(driver, {"path": str(replay_path), "speed": "1x"})
    else:
        driver = load_driver(cfg.driver_name)
        if driver is not None:
            driver = open_driver_or_none(driver, cfg.driver_options)

    app = _build_app(cfg=cfg, workspace=workspace, driver=driver)
    try:
        app.run()
    finally:
        if driver is not None:
            try:
                driver.close()
            except Exception:  # pragma: no cover — defensive
                pass
        # SIGINT (KeyboardInterrupt) escapes ``app.run()`` before
        # ``action_force_quit`` can flush the recording writer. Backstop the
        # flush here so the tail of the .pgnlog isn't lost on Ctrl+C.
        writer = getattr(app, "_writer", None)
        if writer is not None:
            try:
                writer.close()
            except Exception:  # pragma: no cover — defensive
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
