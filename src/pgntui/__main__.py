"""CLI entry point for pgntui."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from importlib import resources
from importlib.metadata import entry_points
from pathlib import Path

from pgntui.app import PgntuiApp
from pgntui.config import Config, _default_workspace, load_config
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalKey, SignalRouter
from pgntui.drivers.base import Driver
from pgntui.drivers.replay import FileReplayDriver
from pgntui.pages.loader import Page, load_page
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
    p.add_argument(
        "--list-ports",
        action="store_true",
        help="list available serial ports (for the actisense-ngt1 driver) and exit",
    )
    p.add_argument(
        "--migrate-workspace",
        action="store_true",
        help="convert old-format container files in --workspace to the new schema and exit",
    )
    sub = p.add_subparsers(dest="command")
    replay = sub.add_parser("replay", help="replay a .pgnlog file")
    replay.add_argument("replay_file")
    probe = sub.add_parser("probe", help="test the NGT-1 connection and exit")
    probe.add_argument(
        "--port", default=None, help="serial port (default: driver.port from config)"
    )
    probe.add_argument(
        "--baud", type=int, default=None, help="speed (default: driver.baud or 115200)"
    )
    probe.add_argument(
        "--seconds", type=float, default=2.0, help="how long to listen (default: 2.0)"
    )
    return p


def parse_args(argv: list[str]) -> argparse.Namespace:
    return build_parser().parse_args(argv)


# ---------------------------------------------------------------------------
# Workspace helpers
# ---------------------------------------------------------------------------


def resolve_workspace(arg: str | None) -> Path:
    return (Path(arg).expanduser() if arg else _default_workspace()).resolve()


def _list_ports() -> int:
    from pgntui.drivers.actisense import list_serial_ports

    ports = list_serial_ports()
    if not ports:
        print("no serial ports found (is pyserial installed and the NGT-1 plugged in?)")
        return 0
    print("available serial ports:")
    for device, desc in ports:
        print(f"  {device:12s} {desc}")
    print('\nset driver.port in config.toml, e.g. port = "COM4" (Windows) or "/dev/ttyUSB0".')
    return 0


def _run_probe(cfg: Config, port: str | None, baud: int | None, seconds: float) -> int:
    from pgntui.drivers.actisense import probe_ngt1

    resolved_port = port or cfg.driver_options.get("port")
    if not resolved_port:
        print(
            "no port given. Pass --port COM4 (run `pgntui --list-ports` to find it) "
            "or set driver.port in config.toml.",
            file=sys.stderr,
        )
        return 2
    resolved_baud = int(baud or cfg.driver_options.get("baud", 115200))
    print(f"probing {resolved_port} @ {resolved_baud} baud for {seconds:g}s…")
    result = probe_ngt1(str(resolved_port), baud=resolved_baud, duration=seconds)
    print(result.summary())
    return 0 if result.ok else 1


def scaffold_example(workspace: Path) -> int:
    """Copy the bundled example workspace into ``workspace``.

    Refuses to clobber an existing directory — the user must point at a fresh
    path or delete the old one.
    """
    if workspace.is_file():
        print(
            f"workspace path {workspace} is a file, not a directory. "
            "Pass --workspace <other> or delete the file.",
            file=sys.stderr,
        )
        return 2
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


def discover_pages(workspace: Path, signal_ids: set[str]) -> list[Page]:
    c_dir = workspace / "containers"
    if not c_dir.is_dir():
        return []
    return [load_page(p, signal_ids) for p in sorted(c_dir.glob("*.json"))]


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
    driver, _ = open_driver_reporting(driver, options)
    return driver


def open_driver_reporting(
    driver: Driver | None, options: dict[str, object]
) -> tuple[Driver | None, str | None]:
    """Open the driver, returning ``(driver, error_message)``.

    On success returns ``(driver, None)``. On failure returns ``(None, msg)`` with
    a friendly, actionable message so the launcher can surface *why* it started
    without a live connection instead of silently degrading to a no-driver UI.
    """
    if driver is None:
        return None, None
    try:
        driver.open(options)
    except Exception as e:
        return None, _driver_open_message(options, e)
    return driver, None


def _driver_open_message(options: dict[str, object], error: Exception) -> str:
    """Turn a driver-open failure into a clear status line."""
    port = options.get("port") or "the serial port"
    text = str(error).lower()
    if "access is denied" in text or "permission" in text or "in use" in text:
        return (
            f"{port} is busy — another app or a previous pgntui still has it. "
            "Close that, then press C to connect."
        )
    return f"Could not open {port}: {error}. Press C to try again."


# ---------------------------------------------------------------------------
# Single-instance guard
# ---------------------------------------------------------------------------


def _instance_lock_path(workspace: Path) -> Path:
    return workspace / "pgntui.lock"


def _pid_alive(pid: int) -> bool:
    """True if a process with ``pid`` is currently running. Cross-platform and
    stdlib-only (no psutil)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        # getattr keeps mypy happy on non-Windows (where ctypes.windll is absent);
        # this branch only runs on Windows anyway. noqa: ruff's B009 wants direct
        # access, but that fails mypy on Linux — the dynamic form is intentional.
        kernel32 = getattr(ctypes, "windll").kernel32  # noqa: B009
        # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000; STILL_ACTIVE = 259.
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return bool(ok) and code.value == 259
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not ours to signal
    return True


def acquire_single_instance(workspace: Path) -> int | None:
    """Take the single-instance lock for ``workspace``.

    Returns ``None`` when the lock is acquired (this is the only instance), or the
    PID of the other *live* pgntui that already holds it. A stale lock (its PID is
    dead) is taken over. Lock-file I/O errors never block startup.
    """
    lock = _instance_lock_path(workspace)
    try:
        if lock.exists():
            try:
                holder = int(lock.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                holder = 0
            if holder and holder != os.getpid() and _pid_alive(holder):
                return holder
        workspace.mkdir(parents=True, exist_ok=True)
        lock.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        return None  # can't write the lock (read-only fs etc.) — don't block
    return None


def release_single_instance(workspace: Path) -> None:
    """Remove the single-instance lock if (and only if) we own it."""
    lock = _instance_lock_path(workspace)
    try:
        if lock.exists() and lock.read_text(encoding="utf-8").strip() == str(os.getpid()):
            lock.unlink()
    except OSError:  # pragma: no cover — defensive
        pass


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
        layout_columns=cfg.layout_columns,
        layout_groups=cfg.layout_groups,
        layout_pages=cfg.layout_pages,
    )


def _build_app(
    cfg: Config,
    workspace: Path,
    driver: Driver | None,
    startup_status: str | None = None,
) -> PgntuiApp:
    try:
        theme = load_builtin(cfg.theme)
    except ThemeLoadError:
        theme = load_builtin("dark")
    signals = discover_signals(workspace)
    pages = discover_pages(workspace, set(signals))
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
        pages=pages,
        write_enabled=cfg.write_enabled,
        record_dir=record_dir,
        debug_buffer=debug_buffer,
        workspace=workspace,
        driver_options=cfg.driver_options,
        layout_columns=cfg.layout_columns,
        layout_groups=cfg.layout_groups,
        layout_pages=cfg.layout_pages,
        startup_status=startup_status,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    workspace = resolve_workspace(args.workspace)

    if args.migrate_workspace:
        from pgntui.pages.migrate import migrate_workspace

        n = migrate_workspace(workspace)
        print(f"migrated {n} container file(s) under {workspace}")
        return 0

    if args.list_ports:
        return _list_ports()

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

    if args.command == "probe":
        return _run_probe(cfg, args.port, args.baud, args.seconds)

    # Set by the live-serial branch below; the finally clause reads them.
    startup_status: str | None = None
    locked = False

    if args.command == "replay":
        replay_path = Path(args.replay_file).expanduser().resolve()
        if not replay_path.exists():
            print(f"replay file not found: {replay_path}", file=sys.stderr)
            return 2
        driver: Driver | None = FileReplayDriver()
        driver = open_driver_or_none(driver, {"path": str(replay_path), "speed": "1x"})
    elif cfg.driver_name == "file-replay" and "path" not in cfg.driver_options:
        # The scaffold ships ``name = "file-replay"`` as a placeholder; it only
        # works via the ``replay`` subcommand (which supplies a path). Launching
        # the UI with it would fail to open for lack of a path, so start with no
        # driver instead of printing a confusing warning. Use the Connection
        # menu (press C) to attach an NGT-1.
        driver = None
    else:
        # Live serial launch (a configured real driver, e.g. the NGT-1). Enforce a
        # single instance so port holders don't pile up: a second launch while one
        # is running would fail to grab the port and confuse the user.
        holder = acquire_single_instance(workspace)
        if holder is not None:
            print(
                f"pgntui is already running (pid {holder}). Quit it (press Q) or "
                "close its window before launching again.",
                file=sys.stderr,
            )
            return 3
        locked = True
        driver = load_driver(cfg.driver_name)
        if driver is not None:
            # Report *why* if the port won't open (busy etc.) so the UI can say so
            # instead of silently starting with no connection.
            driver, startup_status = open_driver_reporting(driver, cfg.driver_options)

    app = _build_app(cfg=cfg, workspace=workspace, driver=driver, startup_status=startup_status)
    try:
        app.run()
    finally:
        if driver is not None:
            try:
                driver.close()
            except Exception:  # pragma: no cover — defensive
                pass
        if locked:
            release_single_instance(workspace)
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
