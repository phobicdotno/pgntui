"""``_writer`` is read by the frame-loop worker thread and written by the
event-loop thread. The audit (A-2) flagged a window where the worker could
snapshot a non-None writer, the main thread could then null + close it, and
the subsequent ``writer.write`` would land on a closed handle.

This test races a synthetic ``_handle_frame`` caller against rapid
``_start_recording`` / ``_stop_recording`` cycles. With the atomic-swap fix
in place the writer either accepts the frame or has already been swapped to
None — never a closed handle write.
"""

from __future__ import annotations

import threading
from pathlib import Path

from pgntui.app import PgntuiApp
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder
from pgntui.decode.router import SignalRouter
from pgntui.drivers.base import Frame
from pgntui.themes.loader import load_builtin


def _make_app(record_dir: Path) -> PgntuiApp:
    return PgntuiApp(
        theme=load_builtin("dark"),
        # No driver -> the frame loop never auto-starts, we drive
        # _handle_frame directly from the test thread.
        driver=None,
        decoder=CanboatDecoder.load_bundled(),
        router=SignalRouter(),
        signals={},
        pages=[],
        debug_buffer=DebugBuffer(),
        record_dir=record_dir,
    )


def _make_frame(i: int) -> Frame:
    return Frame(
        timestamp=1.0 + i * 0.001,
        source_addr=23,
        pgn=127488,
        data=bytes([0x00, i & 0xFF, (i >> 8) & 0xFF, 0x00, 0x00, 0x00, 0xFF, 0xFF]),
    )


def test_handle_frame_vs_stop_recording_no_closed_file_write(tmp_path: Path) -> None:
    """Worker-thread ``_handle_frame`` races event-loop ``_start/_stop_recording``.

    Without the writer lock + atomic-swap pattern, the worker can:
      1. read ``self._writer`` -> non-None
      2. main thread calls ``writer.close()`` and ``self._writer = None``
      3. worker calls ``writer.write(frame)`` -> AssertionError (fh is None)
    With the fix, the worker either sees the still-open writer (and the
    main thread waits behind the lock) or sees None and skips. No exception
    propagates out.
    """
    record_dir = tmp_path / "rec"
    app = _make_app(record_dir)

    iterations = 200
    errors: list[BaseException] = []
    stop_thread_done = threading.Event()

    def worker_writes() -> None:
        try:
            for i in range(iterations):
                app._handle_frame(_make_frame(i))
        except BaseException as e:  # pragma: no cover — failure signal
            errors.append(e)

    def main_toggles() -> None:
        try:
            for _ in range(iterations // 4):
                app._start_recording()
                app._stop_recording()
        except BaseException as e:  # pragma: no cover — failure signal
            errors.append(e)
        finally:
            stop_thread_done.set()

    t_writer = threading.Thread(target=worker_writes, name="frame-loop-sim")
    t_toggler = threading.Thread(target=main_toggles, name="event-loop-sim")
    t_writer.start()
    t_toggler.start()
    t_writer.join(timeout=10)
    t_toggler.join(timeout=10)

    assert not t_writer.is_alive(), "writer thread hung"
    assert not t_toggler.is_alive(), "toggler thread hung"
    assert stop_thread_done.is_set()
    assert errors == [], f"unexpected exception(s) under race: {errors}"

    # End state: at least one of the start/stop cycles produced a closed
    # writer on disk. The writer field itself must be None after the final
    # _stop_recording.
    assert app._writer is None
    assert app._writer_path is None
    # All .pgnlog files written under the rec dir should be closed (file
    # handles released) — we simply check existence as a proxy.
    rec_files = list(record_dir.glob("*.pgnlog"))
    assert rec_files, "no recording files were produced"


def test_stop_recording_is_idempotent(tmp_path: Path) -> None:
    """A second ``_stop_recording`` after the writer has been swapped out must
    be a no-op (no AttributeError on the local ``None`` reference)."""
    app = _make_app(tmp_path / "rec")
    app._start_recording()
    app._stop_recording()
    # Second call must not raise.
    app._stop_recording()
    assert app._writer is None
