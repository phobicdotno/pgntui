"""Textual app shell — tabs, hotkey strip, status bar, frame loop."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Header, RichLog, Static, TabbedContent, TabPane
from textual.worker import Worker

from pgntui.containers.loader import Container
from pgntui.containers.screen import ContainerView
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder, DecodedFrame
from pgntui.decode.router import SignalRouter
from pgntui.drivers.base import Driver, Frame
from pgntui.recording.writer import ActisenseLogWriter
from pgntui.signals.base import (
    AnalogOut,
    DigitalOut,
    Signal,
)
from pgntui.signals.widgets import (
    AnalogInWidget,
    AnalogOutWidget,
    DigitalInWidget,
    DigitalOutWidget,
)
from pgntui.themes.loader import Theme, to_textual_css


class DebugLog(RichLog):
    """RichLog wrapper that knows how to render a DecodedFrame summary."""

    def push_decoded(self, df: DecodedFrame) -> None:
        ts = datetime.fromtimestamp(df.timestamp, tz=UTC).strftime("%H:%M:%S.%f")[:-3]
        name = df.name or "?"
        # Keep the line tight so it fits a typical terminal width.
        fields = ", ".join(f"{k}={v}" for k, v in list(df.fields.items())[:6])
        self.write(f"{ts}  pgn={df.pgn:>6}  src={df.source_addr:>3}  {name}  {fields}")


class PgntuiApp(App[None]):
    """Top-level Textual app.

    Wires a driver -> decoder -> router -> widgets pipeline. The frame loop
    runs in a background thread worker so blocking driver reads (replay sleeps,
    serial waits) never stall the UI event loop.
    """

    CSS = """
    TabbedContent { height: 1fr; }
    #hotkey-strip { height: 1; dock: bottom; background: $primary; }
    #status-bar { height: 1; dock: bottom; }
    #welcome { padding: 1 2; }
    """

    BINDINGS = [
        ("tab", "next_container", "Next"),
        ("shift+tab", "prev_container", "Prev"),
        ("d", "show_debug", "Debug"),
        ("r", "toggle_record", "Record"),
        ("q,ctrl+q", "force_quit", "Quit"),
        ("question_mark", "help", "Help"),
    ]

    def __init__(
        self,
        theme: Theme,
        driver: Driver | None = None,
        decoder: CanboatDecoder | None = None,
        router: SignalRouter | None = None,
        signals: dict[str, Signal] | None = None,
        containers: list[Container] | None = None,
        write_enabled: bool = False,
        record_dir: Path | None = None,
        debug_buffer: DebugBuffer | None = None,
        # Back-compat: older callers (and tests) construct with container_titles=[...].
        # When present, containers + signals are ignored and the app renders title-only
        # placeholder tabs. New callers should prefer the structured args.
        container_titles: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._theme = theme
        self._n2k_driver = driver
        self._decoder = decoder
        self._router = router
        self._signals: dict[str, Signal] = signals or {}
        self._containers: list[Container] = containers or []
        self._write_enabled = write_enabled
        self._record_dir = record_dir
        self._debug_buffer = debug_buffer or DebugBuffer()
        self._container_titles = container_titles
        # Indexed at compose-time so route updates can find widgets fast.
        self._widgets_by_signal: dict[str, list[Widget]] = {}
        # Recording state. ``_writer_lock`` guards the atomic swap between the
        # event-loop thread (which opens/closes the writer) and the frame-loop
        # worker thread (which calls ``writer.write``).
        self._writer: ActisenseLogWriter | None = None
        self._writer_path: Path | None = None
        self._writer_lock: threading.Lock = threading.Lock()
        # Debug pane log instance; populated in compose.
        self._debug_log: DebugLog | None = None
        # Compose-time storage for (container, view) pairs. Populated as
        # ``compose()`` yields each ContainerView so ``_wire_write_callbacks``
        # can hook widgets after mount.
        self._view_pairs: list[tuple[Container, ContainerView]] = []

    # ---- Mount / compose ---------------------------------------------------

    def on_mount(self) -> None:
        self.stylesheet.add_source(to_textual_css(self._theme), read_from=("theme", "theme"))
        self.stylesheet.parse()
        self.refresh_css()
        self._wire_write_callbacks()
        if self._n2k_driver is not None and self._decoder is not None and self._router is not None:
            self.frame_loop()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            with TabbedContent(id="tabs"):
                if self._container_titles is not None:
                    # Legacy path: title-only placeholder tabs (older callers / tests).
                    for title in self._container_titles:
                        with TabPane(title):
                            yield Static(title, classes="signal-title")
                else:
                    for container in self._containers:
                        with TabPane(container.title, id=f"tab-{container.id}"):
                            view = ContainerView(
                                container=container,
                                signals=self._signals,
                                write_enabled=self._write_enabled,
                            )
                            # Stash the view so we can hook widgets after mount.
                            self._view_pairs.append((container, view))
                            yield view
                with TabPane("Debug", id="debug"):
                    if not self._containers and self._container_titles is None:
                        yield Static(_WELCOME_TEXT, id="welcome", markup=True)
                    self._debug_log = DebugLog(
                        highlight=False, markup=False, wrap=False, id="debug-log"
                    )
                    yield self._debug_log
            yield Static(
                "[Tab] Next [D] Debug [R] Rec [Q] Quit",
                id="hotkey-strip",
                markup=False,
            )
            yield Static("status: idle", id="status-bar", markup=False)

    # ---- Frame loop --------------------------------------------------------

    @work(thread=True, exclusive=True, group="frame_loop", name="frame_loop")
    def frame_loop(self) -> None:
        """Pull frames from the driver and dispatch decoded values to widgets.

        Runs in a background thread (``thread=True``) because driver iterators
        block — replay sleeps between frames, serial blocks on bytes. Any UI
        mutation must hop back to the event loop via ``call_from_thread``.
        """
        assert self._n2k_driver is not None
        assert self._decoder is not None
        assert self._router is not None
        try:
            for frame in self._n2k_driver.read_frames():
                self._handle_frame(frame)
        except Exception as e:  # pragma: no cover — defensive
            self.call_from_thread(self._set_status, f"driver error: {e}")

    def _handle_frame(self, frame: Frame) -> None:
        # Called from the worker thread.
        assert self._decoder is not None
        assert self._router is not None
        # Record raw frame first so the recording is faithful even if decoding
        # is incomplete. Snapshot the writer under the lock so the event-loop
        # thread cannot null + close the handle mid-write.
        with self._writer_lock:
            writer = self._writer
        if writer is not None:
            try:
                writer.write(frame)
            except Exception as e:  # pragma: no cover — defensive
                self.call_from_thread(self._set_status, f"rec error: {e}")
        decoded = self._decoder.decode(frame)
        if decoded is None:
            return
        self._debug_buffer.push(decoded)
        if self._debug_log is not None:
            self.call_from_thread(self._debug_log.push_decoded, decoded)
        for update in self._router.route(decoded):
            widgets = self._widgets_by_signal.get(update.signal_id, [])
            for w in widgets:
                self.call_from_thread(self._apply_update, w, update.value)

    @staticmethod
    def _apply_update(widget: Widget, value: object) -> None:
        if isinstance(widget, AnalogInWidget):
            widget.update_value(float(value))  # type: ignore[arg-type]
        elif isinstance(widget, DigitalInWidget):
            # Hand over the raw decoded value — the widget may need the full
            # integer bitfield to extract its configured ``bit``.
            widget.update_value(value)

    # ---- Write callbacks ---------------------------------------------------

    def _wire_write_callbacks(self) -> None:
        """Index widgets by signal id and bind write callbacks for outputs.

        Called from ``on_mount`` so widgets are already attached and accessible
        via ``ContainerView.widgets``.
        """
        self._widgets_by_signal.clear()
        for _container, view in self._view_pairs:
            for ref, widget in view.widgets.items():
                self._widgets_by_signal.setdefault(ref, []).append(widget)
                sig = self._signals.get(ref)
                if sig is None:
                    continue
                if isinstance(widget, AnalogOutWidget) and isinstance(sig, AnalogOut):
                    widget.on_write = self._make_analog_write(sig)
                elif isinstance(widget, DigitalOutWidget) and isinstance(sig, DigitalOut):
                    widget.on_write = self._make_digital_write(sig)

    def _make_analog_write(self, sig: AnalogOut) -> Callable[[float], None]:
        def cb(value: float) -> None:
            if not self._write_enabled or self._n2k_driver is None:
                self._set_status("writes disabled")
                return
            frame = Frame(
                timestamp=datetime.now(tz=UTC).timestamp(),
                source_addr=0,
                pgn=sig.write_pgn,
                data=_encode_analog_payload(value),
            )
            try:
                self._n2k_driver.write_frame(frame)
                self._set_status(f"wrote {sig.id}={value:g}")
            except Exception as e:
                self._set_status(f"write failed: {e}")

        return cb

    def _make_digital_write(self, sig: DigitalOut) -> Callable[[bool], None]:
        def cb(value: bool) -> None:
            if not self._write_enabled or self._n2k_driver is None:
                self._set_status("writes disabled")
                return
            frame = Frame(
                timestamp=datetime.now(tz=UTC).timestamp(),
                source_addr=0,
                pgn=sig.write_pgn,
                data=b"\x01" if value else b"\x00",
            )
            try:
                self._n2k_driver.write_frame(frame)
                self._set_status(f"wrote {sig.id}={'on' if value else 'off'}")
            except Exception as e:
                self._set_status(f"write failed: {e}")

        return cb

    # ---- Status / actions --------------------------------------------------

    def _set_status(self, msg: str) -> None:
        try:
            self.query_one("#status-bar", Static).update(f"status: {msg}")
        except Exception:  # pragma: no cover — pre-mount during tests
            pass

    def action_next_container(self) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.action_next_tab()  # type: ignore[attr-defined]  # Textual provides at runtime

    def action_prev_container(self) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.action_previous_tab()  # type: ignore[attr-defined]  # Textual provides at runtime

    def action_show_debug(self) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = "debug"

    def action_toggle_record(self) -> None:
        if self._writer is not None:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        record_dir = self._record_dir or Path.cwd()
        record_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
        path = record_dir / f"{stamp}.pgnlog"
        writer = ActisenseLogWriter(path)
        writer.open()
        # Install under the lock so worker-thread reads of self._writer see a
        # consistent (writer, path) pair.
        with self._writer_lock:
            self._writer = writer
            self._writer_path = path
        self._set_status(f"REC -> {path.name}")

    def _stop_recording(self) -> None:
        # Atomic swap: null self._writer FIRST (under the lock) so any worker
        # thread that snapshots after this point sees None. Only then close
        # the local handle. Prevents writer.write() landing on a closed file.
        with self._writer_lock:
            writer, self._writer = self._writer, None
            self._writer_path = None
        if writer is None:
            return
        try:
            writer.close()
        finally:
            self._set_status("idle")

    def action_help(self) -> None:
        self._set_status("help: Tab/D/R/Q")

    def action_force_quit(self) -> None:
        """Quit immediately, bypassing Textual's ctrl+q confirmation toast.

        Order matters here:
          1. Flush + close the recording writer so the on-disk tail is intact.
          2. Cancel the frame-loop worker so it stops reading from the (about
             to be closed) driver and stops posting ``call_from_thread`` work
             into an event loop that is about to die.
          3. Exit the Textual app.
        """
        # Make sure recording is flushed cleanly before we exit.
        if self._writer is not None:
            try:
                self._stop_recording()
            except Exception:  # pragma: no cover — defensive
                pass
        # Cancel the frame_loop worker. Textual 8.x WorkerManager iterates as
        # a set; look up by group name. ``cancel()`` on a thread-worker only
        # flips state — the actual read loops cooperate via their own stop
        # events (see ``NGT1Driver._stop`` / ``FileReplayDriver._stop``).
        try:
            for worker in list(self.workers):
                if self._is_frame_loop_worker(worker):
                    worker.cancel()
        except Exception:  # pragma: no cover — defensive
            pass
        self.exit()

    @staticmethod
    def _is_frame_loop_worker(worker: Worker[None]) -> bool:
        return worker.group == "frame_loop" or worker.name == "frame_loop"


_WELCOME_TEXT = """[b]pgntui[/b] — no workspace configured

To get started:
  [b]pgntui --example[/b]            scaffold an example workspace at the OS default location
  [b]pgntui replay <file.pgnlog>[/b]  play a recording into the TUI
  [b]pgntui --help[/b]               full options

Once a workspace exists, container tabs will appear above and incoming PGN
frames will scroll here.

Press [b]Q[/b] to quit."""


def _encode_analog_payload(value: float) -> bytes:
    """Minimal encoder used by the analog write callback.

    Real-world NMEA 2000 encoders need per-PGN resolution/scaling. This default
    just packs the value as little-endian uint16 so the wire format is
    deterministic; production users should override by intercepting
    ``on_write`` directly.
    """
    v = max(0, min(0xFFFF, int(round(value))))
    return v.to_bytes(2, "little")


__all__ = ["DebugLog", "PgntuiApp"]
