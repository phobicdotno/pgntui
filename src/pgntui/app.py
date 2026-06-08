"""Textual app shell — tabs, hotkey strip, status bar, frame loop."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from textual import events, on, work
from textual.app import App, ComposeResult
from textual.containers import Container as TextualContainer
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
)
from textual.worker import Worker

from pgntui import about
from pgntui.debug.tab import DebugBuffer
from pgntui.decode.canboat import CanboatDecoder, DecodedFrame
from pgntui.decode.router import SignalRouter
from pgntui.drivers.base import Driver, Frame
from pgntui.pages.auto import AutoPageBuilder
from pgntui.pages.loader import Page
from pgntui.pages.view import PageView
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
from pgntui.themes.loader import (
    Theme,
    ThemeLoadError,
    list_builtin,
    load_builtin,
    to_textual_css,
    to_textual_theme,
)


def _frame_fields(df: DecodedFrame) -> str:
    """Compact ``k=v, k=v`` summary of a decoded frame's first few fields."""
    return ", ".join(f"{k}={v}" for k, v in list(df.fields.items())[:6])


def _frame_time(df: DecodedFrame) -> str:
    return datetime.fromtimestamp(df.timestamp, tz=UTC).strftime("%H:%M:%S.%f")[:-3]


class DebugLog(RichLog):
    """Streaming (trace) view: every decoded frame appended as a new line, in
    arrival order — the chronological scrollback."""

    def push_decoded(self, df: DecodedFrame) -> None:
        name = df.name or "?"
        # Keep the line tight so it fits a typical terminal width.
        self.write(
            f"{_frame_time(df)}  pgn={df.pgn:>6}  src={df.source_addr:>3}  "
            f"{name}  {_frame_fields(df)}"
        )


class DebugAggregate(DataTable[str]):
    """Aggregated (coalesced) view: one row per ``(PGN, source)``, updated in
    place with the latest values, last-seen time, and a hit count — so repeated
    frames stack onto a single line instead of scrolling. The counterpart to
    :class:`DebugLog`'s streaming trace.
    """

    DEFAULT_CSS = """
    DebugAggregate { height: 1fr; }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Row keys (``"<pgn>:<src>"``) already present, so we know update vs add.
        self._seen: set[str] = set()

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_column("Time", key="time")
        self.add_column("PGN", key="pgn")
        self.add_column("Src", key="src")
        self.add_column("Name", key="name")
        self.add_column("Count", key="count")
        self.add_column("Fields", key="fields")

    def push_decoded(self, df: DecodedFrame) -> None:
        key = f"{df.pgn}:{df.source_addr}"
        name = df.name or "?"
        fields = _frame_fields(df)
        ts = _frame_time(df)
        if key in self._seen:
            count = int(str(self.get_cell(key, "count"))) + 1
            self.update_cell(key, "time", ts)
            self.update_cell(key, "name", name)
            self.update_cell(key, "count", str(count))
            self.update_cell(key, "fields", fields)
        else:
            self._seen.add(key)
            self.add_row(ts, str(df.pgn), str(df.source_addr), name, "1", fields, key=key)

    def clear_frames(self) -> None:
        self.clear()
        self._seen.clear()


# The menu bar's contents: each top-level menu maps to a list of
# ``(label, action_name, key)`` rows. ``action_name`` resolves to ``action_*`` on
# the app, so clicking a menu item and pressing its key share one code path.
_MENUS: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...] = (
    ("File", (("Record on/off", "toggle_record", "R"), ("Quit", "force_quit", "Q"))),
    ("Connection", (("Connect…", "connection", "C"),)),
    (
        "View",
        (
            ("Debug", "show_debug", "D"),
            ("Debug: trace / aggregate", "toggle_debug_view", "G"),
            ("Settings…", "config", "S"),
        ),
    ),
    ("Help", (("About", "about", "A"), ("Keyboard help", "help", "?"))),
)


class MenuItem(Static):
    """One clickable row in an open menu: ``label … key``."""

    DEFAULT_CSS = """
    MenuItem { width: 100%; height: 1; padding: 0 1; }
    MenuItem:hover { background: $accent; color: $background; text-style: bold; }
    """

    def __init__(self, label: str, key: str, action: str, width: int) -> None:
        # Pad the label so every shortcut lines up in a column on the right.
        super().__init__(f"{label:<{width}}   {key}", markup=False, id=f"menu-item-{action}")
        self._action = action

    def on_click(self, event: events.Click) -> None:
        event.stop()  # don't let it bubble to the screen's close-on-click
        screen = self.screen
        if isinstance(screen, MenuScreen):
            screen.select(self._action)


class MenuScreen(ModalScreen[None]):
    """A dropdown for one top-level menu, opened under its title."""

    DEFAULT_CSS = """
    MenuScreen { align: left top; background: $background 0%; }
    MenuScreen #menu-dropdown {
        width: auto;
        height: auto;
        border: round $accent;
        background: $surface;
        padding: 0 1;
    }
    """

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, items: tuple[tuple[str, str, str], ...], x: int) -> None:
        super().__init__()
        self._items = items
        self._x = x

    def compose(self) -> ComposeResult:
        label_w = max((len(label) for label, _, _ in self._items), default=4)
        dropdown = Vertical(
            *(MenuItem(label, key, action, label_w) for label, action, key in self._items),
            id="menu-dropdown",
        )
        # Pin the width to the content: an auto-width box with width:100% children
        # collapses, so size it from the row text (label + 3 spaces + key) plus the
        # border (2) and padding (2).
        dropdown.styles.width = label_w + 1 + 3 + 2 + 2 + 2
        # Sit just under the menu bar, left-aligned with the clicked title.
        dropdown.styles.offset = (max(self._x, 0), 1)
        yield dropdown

    def on_click(self) -> None:
        # A click that reaches the screen missed every item -> close the menu.
        self.dismiss()

    def select(self, action: str) -> None:
        """Run the chosen action after the menu has closed (so a dialog it opens
        isn't immediately popped along with this menu)."""
        fn = getattr(self.app, f"action_{action}", None)
        self.dismiss()
        if fn is not None:
            self.app.call_after_refresh(fn)


class MenuTitle(Static):
    """A clickable top-level menu name in the title bar."""

    DEFAULT_CSS = """
    MenuTitle { width: auto; padding: 0 2; }
    MenuTitle:hover { background: $accent; color: $background; text-style: bold; }
    """

    def __init__(self, name: str, items: tuple[tuple[str, str, str], ...], **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._items = items

    def on_click(self) -> None:
        self.app.push_screen(MenuScreen(self._items, self.region.x))


class TopBar(Horizontal):
    """One-line title bar: the ``File Connection View Help`` menu bar on the left
    and the centered ``PgnTui — NMEA 2000 reader — vX.Y.Z — © …`` title."""

    DEFAULT_CSS = """
    TopBar { dock: top; height: 1; background: $surface; }
    TopBar #topbar-left { width: auto; height: 1; }
    TopBar #app-title { width: 1fr; content-align: center middle; text-style: bold; }
    """

    def compose(self) -> ComposeResult:
        yield Horizontal(
            *(MenuTitle(name, items, id=f"menu-{name.lower()}") for name, items in _MENUS),
            id="topbar-left",
        )
        yield Static(about.header_title(), id="app-title")


class AboutScreen(ModalScreen[None]):
    """Modal dialog: app name, version, and a short changelog."""

    DEFAULT_CSS = """
    AboutScreen { align: center middle; }
    AboutScreen #about-dialog {
        width: 80;
        max-width: 95%;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    AboutScreen #about-head { text-style: bold; }
    AboutScreen #about-hint { color: $accent; margin-top: 1; }
    """

    BINDINGS = [("escape,q,a", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        from pgntui import __version__

        body = [
            f"{about.APP_NAME} — {about.TAGLINE}",
            f"version {__version__}",
            about.COPYRIGHT,
            "",
            "What's new:",
        ]
        body += [f"  {line}" for line in about.changelog_lines()]
        yield TextualContainer(
            # markup=False: changelog text is literal (entries may contain
            # ``[`` / ``]``, which Rich markup would otherwise eat).
            Static("\n".join(body), id="about-head", markup=False),
            Static("[Esc] close", id="about-hint", markup=False),
            id="about-dialog",
        )


BAUD_RATES = (4800, 9600, 19200, 38400, 57600, 115200, 230400)


class ConnectionScreen(ModalScreen[None]):
    """Pick a serial port + speed, test the NGT-1, then Save or Connect."""

    DEFAULT_CSS = """
    ConnectionScreen { align: center middle; }
    ConnectionScreen #conn-dialog {
        width: 72;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    ConnectionScreen #conn-title { text-style: bold; margin-bottom: 1; }
    ConnectionScreen .conn-label { color: $accent; margin-top: 1; }
    ConnectionScreen #conn-buttons { height: auto; margin-top: 1; }
    ConnectionScreen Button { margin: 0 1 0 0; }
    ConnectionScreen #conn-result { margin-top: 1; height: auto; min-height: 2; }
    """

    BINDINGS = [("escape", "dismiss", "Close")]

    # Seconds to keep the dialog up after a successful Connect (override in tests).
    AUTO_CLOSE_SECONDS = 1.2

    def __init__(
        self, *, workspace: Path | None, current_port: str | None, current_baud: int | None
    ) -> None:
        super().__init__()
        self._workspace = workspace
        self._current_port = current_port
        self._current_baud = current_baud if current_baud in BAUD_RATES else 115200

    def compose(self) -> ComposeResult:
        from pgntui.drivers.actisense import list_serial_ports

        ports = list_serial_ports()
        port_options = [(f"{dev}  {desc}".rstrip(), dev) for dev, desc in ports]
        known = {dev for dev, _ in ports}
        # Only preselect when the saved port is actually present; otherwise leave
        # the Select blank (its default NULL state).
        port_kwargs: dict[str, Any] = {}
        if self._current_port in known:
            port_kwargs["value"] = self._current_port
        yield TextualContainer(
            Static("NMEA 2000 connection", id="conn-title"),
            Static("Serial port", classes="conn-label"),
            Select(
                port_options,
                prompt="(no port — plug in the NGT-1)",
                id="port-select",
                **port_kwargs,
            ),
            Static("Speed (baud)", classes="conn-label"),
            Select(
                [(str(b), b) for b in BAUD_RATES],
                value=self._current_baud,
                allow_blank=False,
                id="baud-select",
            ),
            Horizontal(
                Button("Test", id="conn-test", variant="primary"),
                Button("Save", id="conn-save"),
                Button("Connect", id="conn-connect", variant="success"),
                Button("Close", id="conn-close"),
                id="conn-buttons",
            ),
            Static("Pick a port and press Test.", id="conn-result", markup=False),
            id="conn-dialog",
        )

    # ---- helpers -----------------------------------------------------------

    def _selected_port(self) -> str | None:
        value = self.query_one("#port-select", Select).value
        return None if value is Select.NULL else str(value)

    def _selected_baud(self) -> int:
        return int(self.query_one("#baud-select", Select).value)  # type: ignore[arg-type]

    def _set_result(self, text: str) -> None:
        self.query_one("#conn-result", Static).update(text)

    # ---- buttons -----------------------------------------------------------

    @on(Button.Pressed, "#conn-close")
    def _on_close(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#conn-test")
    def _on_test(self) -> None:
        port = self._selected_port()
        if not port:
            self._set_result("Pick a serial port first.")
            return
        baud = self._selected_baud()
        self._set_result(f"Testing {port} @ {baud} baud — listening for 2s…")
        self._probe(port, baud)

    @work(thread=True, exclusive=True, group="conn_probe")
    def _probe(self, port: str, baud: int) -> None:
        from pgntui.drivers.actisense import probe_ngt1

        result = probe_ngt1(port, baud, duration=2.0)
        self.app.call_from_thread(self._set_result, result.summary())

    @on(Button.Pressed, "#conn-save")
    def _on_save(self) -> None:
        port = self._selected_port()
        if not port:
            self._set_result("Pick a serial port first.")
            return
        if self._workspace is None:
            self._set_result("No workspace to save into.")
            return
        from pgntui.config import write_driver_settings

        baud = self._selected_baud()
        write_driver_settings(self._workspace / "config.toml", "actisense-ngt1", port, baud)
        self._set_result(f"Saved {port} @ {baud} to config.toml. Press Connect, or restart pgntui.")

    @on(Button.Pressed, "#conn-connect")
    def _on_connect(self) -> None:
        port = self._selected_port()
        if not port:
            self._set_result("Pick a serial port first.")
            return
        baud = self._selected_baud()
        ok, message = self.app.connect_ngt1(port, baud)  # type: ignore[attr-defined]
        self._set_result(message)
        if ok:
            # Auto-close shortly so the user sees the live dashboard. The timer
            # callback must NOT return the AwaitComplete from dismiss(): Textual
            # would await it inside this screen's message pump and raise
            # ScreenError. Calling dismiss() and returning None pops safely.
            self.set_timer(self.AUTO_CLOSE_SECONDS, self._close)

    def _close(self) -> None:
        self.dismiss()


class ConfigScreen(ModalScreen[None]):
    """The ``☰ Menu`` config panel: switch theme live (and persist it), show
    the current connection/write state, and jump to the Connection dialog.

    The theme picker applies the selected theme immediately as a live preview.
    ``Save`` writes it to ``config.toml``; closing without saving reverts to the
    theme that was active when the menu opened.
    """

    DEFAULT_CSS = """
    ConfigScreen { align: center middle; }
    ConfigScreen #config-dialog {
        width: 64;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    ConfigScreen #config-title { text-style: bold; margin-bottom: 1; }
    ConfigScreen .config-label { color: $accent; margin-top: 1; }
    ConfigScreen #config-info { margin-top: 1; height: auto; min-height: 2; }
    ConfigScreen #config-buttons { height: auto; margin-top: 1; }
    ConfigScreen Button { margin: 0 1 0 0; }
    """

    BINDINGS = [("escape", "cancel", "Close")]

    def __init__(
        self,
        *,
        workspace: Path | None,
        current_theme: str,
        themes: list[tuple[str, str]],
        info_lines: list[str],
    ) -> None:
        super().__init__()
        self._workspace = workspace
        self._original_theme = current_theme
        self._current_theme = current_theme
        self._themes = themes
        self._info_lines = info_lines

    def compose(self) -> ComposeResult:
        # If the active theme somehow isn't in the list, leave Select blank so it
        # doesn't raise on an unknown value.
        theme_ids = {tid for _, tid in self._themes}
        select_kwargs: dict[str, Any] = {"allow_blank": False}
        if self._current_theme in theme_ids:
            select_kwargs["value"] = self._current_theme
        yield TextualContainer(
            Static("Configuration", id="config-title"),
            Static("Theme", classes="config-label"),
            Select(
                [(title, tid) for title, tid in self._themes],
                id="theme-select",
                **select_kwargs,
            ),
            Static("\n".join(self._info_lines), id="config-info", markup=False),
            Horizontal(
                Button("Connection…", id="config-connection", variant="primary"),
                Button("Save", id="config-save", variant="success"),
                Button("Close", id="config-close"),
                id="config-buttons",
            ),
            id="config-dialog",
        )

    @on(Select.Changed, "#theme-select")
    def _on_theme_changed(self, event: Select.Changed) -> None:
        value = event.value
        if value is Select.NULL:
            return
        self._current_theme = str(value)
        # Live preview: re-theme the whole app immediately.
        self.app.apply_theme(self._current_theme)  # type: ignore[attr-defined]

    @on(Button.Pressed, "#config-connection")
    def _on_connection(self) -> None:
        self.app.action_connection()  # type: ignore[attr-defined]

    @on(Button.Pressed, "#config-save")
    def _on_save(self) -> None:
        if self._workspace is not None:
            from pgntui.config import write_theme

            write_theme(self._workspace / "config.toml", self._current_theme)
        self._original_theme = self._current_theme  # keep the preview on close
        self.dismiss()

    @on(Button.Pressed, "#config-close")
    def _on_close(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        # Revert the live preview if the theme was changed but not saved.
        if self._current_theme != self._original_theme:
            self.app.apply_theme(self._original_theme)  # type: ignore[attr-defined]
        self.dismiss()


# The single content tab that stacks every source page as a labelled section.
_CONTENT_TAB_ID = "tab-content"


class PgntuiApp(App[None]):
    """Top-level Textual app.

    Wires a driver -> decoder -> router -> widgets pipeline. The frame loop
    runs in a background thread worker so blocking driver reads (replay sleeps,
    serial waits) never stall the UI event loop.
    """

    CSS = """
    TabbedContent { height: 1fr; }
    /* Footer is one docked bar: the hotkey hints fill the left, the status sits at
       the right. A single row so they share the bar (two separate ``dock: bottom``
       widgets would land on the same row and overlap, hiding the hints). $boost is
       a subtle overlay on the normal background, so the normal foreground text
       stays readable on every theme (a bright $primary fill did not). */
    #footer { dock: bottom; height: 1; background: $boost; color: $foreground; }
    #hotkey-strip { width: 1fr; height: 1; }
    #status-bar { width: auto; height: 1; padding: 0 1; }
    #welcome { padding: 1 2; }
    """

    BINDINGS = [
        ("tab", "next_container", "Next"),
        ("shift+tab", "prev_container", "Prev"),
        ("up", "focus_prev_signal", "Up"),
        ("down", "focus_next_signal", "Down"),
        ("plus", "toggle_sparkline", "Spark"),
        ("1", "columns_one", "1col"),
        ("2", "columns_default", "2col"),
        ("3", "columns_three", "3col"),
        # Shift+1/2/3 arrange the group boxes into 1/2/3 columns. Terminals report
        # shifted digits as their symbol, and the symbol is keyboard-layout
        # dependent, so bind both the US (@) and Nordic (") forms of Shift+2.
        ("exclamation_mark", "group_columns_one", "Grp1"),
        ("at,quotation_mark", "group_columns_two", "Grp2"),
        ("number_sign", "group_columns_three", "Grp3"),
        # Page columns: F1/F2/F3 work even on terminals that don't report
        # Ctrl+digit (legacy mode only sends control codes for Ctrl+letter); the
        # ctrl+digit aliases still fire where the enhanced keyboard protocol is on.
        ("f1,ctrl+1", "page_columns_one", "Pg1"),
        ("f2,ctrl+2", "page_columns_two", "Pg2"),
        ("f3,ctrl+3", "page_columns_three", "Pg3"),
        ("d", "show_debug", "Debug"),
        ("g", "toggle_debug_view", "Group"),
        ("r", "toggle_record", "Record"),
        # Instance switch: , / . work on every keyboard (the [ ] aliases need
        # AltGr on Nordic layouts, so keep both).
        ("comma,left_square_bracket", "prev_instance", "Inst-"),
        ("full_stop,right_square_bracket", "next_instance", "Inst+"),
        ("c", "connection", "Connection"),
        ("s", "config", "Config"),
        ("a", "about", "About"),
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
        pages: list[Page] | None = None,
        write_enabled: bool = False,
        record_dir: Path | None = None,
        debug_buffer: DebugBuffer | None = None,
        workspace: Path | None = None,
        driver_options: dict[str, Any] | None = None,
        # Last-used layout (restored from config), applied to every view on mount.
        layout_columns: int | None = None,
        layout_groups: int = 1,
        layout_pages: int = 1,
        # Optional message shown in the status bar on mount (e.g. a port-busy
        # notice when the configured driver couldn't auto-connect at launch).
        startup_status: str | None = None,
        # Back-compat: older callers (and tests) construct with page_titles=[...].
        # When present, pages + signals are ignored and the app renders title-only
        # placeholder tabs. New callers should prefer the structured args.
        page_titles: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._theme = theme
        # Workspace + last-known driver options, so the Connection menu can show
        # the current port/speed as defaults and save changes back to config.toml.
        self._workspace = workspace
        self._driver_options: dict[str, Any] = driver_options or {}
        self._n2k_driver = driver
        self._decoder = decoder
        self._router = router
        self._signals: dict[str, Signal] = signals or {}
        self._pages: list[Page] = pages or []
        self._write_enabled = write_enabled
        self._record_dir = record_dir
        self._debug_buffer = debug_buffer or DebugBuffer()
        self._page_titles = page_titles
        # Shared sparkline clock — the latest frame timestamp seen. Expanded
        # sparklines render their window ending at this value.
        self._clock: float = 0.0
        # Indexed at compose-time so route updates can find widgets fast.
        self._widgets_by_signal: dict[str, list[Widget]] = {}
        # widget -> its PageView, for per-page instance filtering.
        self._view_of_widget: dict[Widget, PageView] = {}
        # Recording state. ``_writer_lock`` guards the atomic swap between the
        # event-loop thread (which opens/closes the writer) and the frame-loop
        # worker thread (which calls ``writer.write``).
        self._writer: ActisenseLogWriter | None = None
        self._writer_path: Path | None = None
        self._writer_lock: threading.Lock = threading.Lock()
        # Debug pane widgets; populated in compose. The Debug tab shows one at a
        # time — the streaming log by default, the aggregated table on toggle.
        self._debug_log: DebugLog | None = None
        self._debug_aggregate: DebugAggregate | None = None
        # Whether the Debug tab is the active one. Set on the UI thread from the
        # TabActivated handler; read (atomic bool) from the frame-loop worker so it
        # only does the per-frame UI hop to the Debug views when they're visible.
        # The capped DebugBuffer keeps accumulating regardless, and the views are
        # repopulated from it when Debug is opened.
        self._debug_active: bool = False
        # Likewise for the Auto tab: only build/update its boxes while it's the
        # active tab (rebuilt from the buffer when opened).
        self._auto_active: bool = False
        # Compose-time storage for (page, view) pairs. Populated as ``compose()``
        # yields each PageView so ``_wire_write_callbacks`` can hook widgets
        # after mount.
        self._page_views: list[tuple[Page, PageView]] = []
        # The grid that arranges the content sections; F1/F2/F3 set its columns.
        self._page_grid: Grid | None = None
        # Last-used layout, restored on mount and re-persisted on every change so
        # the [1/2/3], Shift+1/2/3 and F1/F2/F3 choices survive a restart.
        self._saved_signal_cols: int | None = layout_columns
        self._saved_group_cols: int = layout_groups
        self._saved_page_cols: int = layout_pages
        self._page_cols: int = layout_pages
        self._startup_status = startup_status
        # Auto page (built at runtime from the live stream) — only with a driver.
        self._auto_view: PageView | None = None
        self._auto_builder: AutoPageBuilder | None = None

    # ---- Mount / compose ---------------------------------------------------

    def on_mount(self) -> None:
        # Drive Textual's own chrome (header, tabs, footer, scrollbars) from the
        # pgntui theme so the whole screen is themed, not just widget content.
        # Without this, the chrome stays on Textual's default theme and the UI
        # looks half-themed (pgntui colors inside, catppuccin outside).
        textual_theme = to_textual_theme(self._theme)
        self.register_theme(textual_theme)
        self.theme = textual_theme.name
        # Also set the OS terminal title.
        self.title = about.header_title()
        self.stylesheet.add_source(to_textual_css(self._theme), read_from=("theme", "theme"))
        self.stylesheet.parse()
        self.refresh_css()
        self._wire_write_callbacks()
        if self._auto_view is not None:
            self._auto_builder = AutoPageBuilder(self._auto_view, theme=self._theme)
        self._apply_saved_layout()
        if self._startup_status:
            self._set_status(self._startup_status)
        # Repaint expanded sparklines once a second so a stopped signal scrolls
        # left into trailing gaps even when no new frames arrive for it.
        self.set_interval(1.0, self._tick_sparklines)
        if self._n2k_driver is not None and self._decoder is not None and self._router is not None:
            self.frame_loop()

    def compose(self) -> ComposeResult:
        yield TopBar()
        with Vertical():
            with TabbedContent(id="tabs"):
                if self._page_titles is not None:
                    # Legacy path: title-only placeholder tabs (older callers / tests).
                    for title in self._page_titles:
                        with TabPane(title):
                            yield Static(title, classes="signal-title")
                else:
                    if self._pages:
                        # One "Main" tab holds every source page as a labelled
                        # section in a grid, so Ctrl+1/2/3 can lay the sections out
                        # in 1/2/3 page-columns (the box & signal column toggles
                        # nest inside each section).
                        self._page_grid = Grid(id="page-grid")
                        self._page_grid.styles.grid_size_columns = self._page_cols
                        self._page_grid.styles.grid_rows = "auto"
                        self._page_grid.styles.height = "auto"
                        self._page_grid.styles.grid_gutter_vertical = 1
                        self._page_grid.styles.grid_gutter_horizontal = 1
                        with (
                            TabPane("Main", id=_CONTENT_TAB_ID),
                            VerticalScroll(id="content-scroll"),
                            self._page_grid,
                        ):
                            for page in self._pages:
                                # An instance-switchable page (Engine with Stb/Port/
                                # generators) becomes one fixed section per instance,
                                # each accepting only its instance's frames so the
                                # readouts don't jump between engines.
                                if page.instances:
                                    for opt in page.instances:
                                        iview = PageView(
                                            page=page,
                                            signals=self._signals,
                                            write_enabled=self._write_enabled,
                                            theme=self._theme,
                                            section_title=opt.label,
                                            fixed_instance=opt.id,
                                        )
                                        self._page_views.append((page, iview))
                                        yield iview
                                    continue
                                view = PageView(
                                    page=page,
                                    signals=self._signals,
                                    write_enabled=self._write_enabled,
                                    theme=self._theme,
                                    section_title=page.title,
                                )
                                # PageView pins its own height (_size_box_grid_rows)
                                # so it measures right inside a page-grid cell.
                                self._page_views.append((page, view))
                                yield view
                    if self._n2k_driver is not None:
                        # Auto tab: auto-populates from the live stream. Only with
                        # a driver (skipping it keeps no-driver frame tests clean).
                        auto_page = Page(id="auto", title="Auto", containers=(), generated=True)
                        self._auto_view = PageView(
                            page=auto_page,
                            signals=self._signals,
                            write_enabled=self._write_enabled,
                            theme=self._theme,
                            masonry=True,  # top-packed columns (no ragged gaps)
                        )
                        with TabPane("Auto", id="tab-auto"):
                            yield self._auto_view
                with TabPane("Debug", id="debug"):
                    if not self._pages and self._page_titles is None:
                        yield Static(_WELCOME_TEXT, id="welcome", markup=True)
                    # Cap the scrollback: a RichLog keeps every line in memory,
                    # so on a busy bus an unbounded log grows without limit and
                    # eventually freezes when rendered. 5000 lines is plenty of
                    # history; older lines are discarded. (The aggregate view is
                    # naturally bounded — one row per PGN/source.)
                    self._debug_log = DebugLog(
                        highlight=False, markup=False, wrap=False, max_lines=5000, id="debug-log"
                    )
                    yield self._debug_log
                    self._debug_aggregate = DebugAggregate(id="debug-aggregate")
                    # Stream view is the default; the aggregate starts hidden and
                    # is revealed by the [G] toggle.
                    self._debug_aggregate.display = False
                    yield self._debug_aggregate
            with Horizontal(id="footer"):
                # Navigation + layout hints live here; the action keys (Debug,
                # Record, Connect, Settings, About, Quit) now live in the menu bar.
                yield Static(
                    "[Tab] Page  [,/.] Inst  [↑/↓] Sig  [+] Spark  "
                    "[1/2/3] Cols  [Shift+1/2/3] Box cols  [F1/F2/F3] Pages  "
                    "[Menu] File/View/Help",
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
        # Worker-thread write of a plain float, read by the UI-thread repaint
        # timer. Safe under CPython (a single attribute store is atomic) and the
        # value only moves forward (max), so the worst case on a race is a
        # one-frame-stale sparkline window.
        self._clock = max(self._clock, decoded.timestamp)
        self._debug_buffer.push(decoded)
        # Only do the per-frame UI hop to the Debug views when the Debug tab is
        # visible — otherwise it floods the event loop on a busy bus for a view
        # nobody is looking at. When hidden, the capped DebugBuffer still records
        # everything; the views are rebuilt from it when Debug is opened.
        if self._debug_active:
            if self._debug_log is not None:
                self.call_from_thread(self._debug_log.push_decoded, decoded)
            if self._debug_aggregate is not None:
                self.call_from_thread(self._debug_aggregate.push_decoded, decoded)
        # Same as Debug: only build/update the Auto boxes while Auto is visible
        # (it's rebuilt from the buffer on open). Routing to the authored pages
        # below always runs — that's the app's main job.
        if self._auto_active and self._auto_builder is not None:
            self.call_from_thread(self._auto_builder.ingest, decoded)
        for update in self._router.route(decoded):
            for w in self._widgets_by_signal.get(update.signal_id, []):
                # Instance-switchable pages show one source at a time, so skip
                # frames whose Instance isn't the one this view is showing.
                view = self._view_of_widget.get(w)
                if (
                    view is not None
                    and view.page.instances
                    and view.active_instance_id != update.instance
                ):
                    continue
                self.call_from_thread(self._apply_update, w, update.value, update.timestamp)

    @staticmethod
    def _apply_update(widget: Widget, value: object, ts: float | None = None) -> None:
        if isinstance(widget, AnalogInWidget):
            widget.update_value(float(value), ts)  # type: ignore[arg-type]
        elif isinstance(widget, DigitalInWidget):
            # Hand over the raw decoded value — the widget may need the full
            # integer bitfield to extract its configured ``bit``.
            widget.update_value(value, ts)

    # ---- Write callbacks ---------------------------------------------------

    def _wire_write_callbacks(self) -> None:
        """Index widgets by signal id and bind write callbacks for outputs.

        Called from ``on_mount`` so widgets are already attached and accessible
        via ``PageView.widgets``.
        """
        self._widgets_by_signal.clear()
        self._view_of_widget.clear()
        for _page, view in self._page_views:
            for ref, widget in view.widgets.items():
                self._widgets_by_signal.setdefault(ref, []).append(widget)
                self._view_of_widget[widget] = view
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

    def action_toggle_sparkline(self) -> None:
        w = self.focused
        if isinstance(w, (AnalogInWidget, DigitalInWidget)):
            w.toggle_sparkline()

    def action_columns_one(self) -> None:
        self._set_signal_columns(1)

    def action_columns_default(self) -> None:
        self._set_signal_columns(2)

    def action_columns_three(self) -> None:
        self._set_signal_columns(3)

    def _set_signal_columns(self, n: int) -> None:
        for view in self._active_views():
            view.set_columns(n)
        self._saved_signal_cols = n
        self._persist_layout()

    def action_group_columns_one(self) -> None:
        self._set_group_columns(1)

    def action_group_columns_two(self) -> None:
        self._set_group_columns(2)

    def action_group_columns_three(self) -> None:
        self._set_group_columns(3)

    def _set_group_columns(self, n: int) -> None:
        for view in self._active_views():
            self._set_box_columns(view, n)
        self._saved_group_cols = n
        # Group columns derive the signal density (set_group_columns → set_columns
        # 4-n); clear the saved signal override so restore reproduces that, unless
        # the user later picks a signal column explicitly.
        self._saved_signal_cols = None
        self._persist_layout()

    def _set_box_columns(self, view: PageView, n: int) -> None:
        """Apply ``n`` box columns to ``view``. A masonry view (Auto) can't reflow
        in place — Textual destroys a box's widgets when it's reparented — so it
        rebuilds its columns and re-ingests from the buffer in a worker; a grid
        view sets the column count synchronously."""
        if view.masonry:
            self.run_worker(self._relayout_auto(view, n), group="auto-relayout", exclusive=True)
        else:
            view.set_group_columns(n)

    async def _relayout_auto(self, view: PageView, n: int) -> None:
        await view.set_masonry_columns(n)
        if self._auto_builder is not None:
            self._auto_builder.reset()
            self._populate_auto_from_buffer()

    def action_page_columns_one(self) -> None:
        self._set_page_columns(1)

    def action_page_columns_two(self) -> None:
        self._set_page_columns(2)

    def action_page_columns_three(self) -> None:
        self._set_page_columns(3)

    def _set_page_columns(self, n: int) -> None:
        """F1/F2/F3 → lay content out in ``n`` columns.

        On the Main tab this arranges the section grid (Nav/Engine/Main columns;
        sections pin their own height so the grid's auto rows size correctly). The
        Auto tab has no section grid — it is one view of many PGN boxes — so there
        F1/F2/F3 arrange those boxes into ``n`` columns instead (same as
        Shift+1/2/3), which is what "page columns" means on that page.
        """
        try:
            active = self.query_one(TabbedContent).active
        except Exception:  # pragma: no cover — pre-mount
            return
        if active == _CONTENT_TAB_ID and self._page_grid is not None:
            self._page_cols = n
            self._page_grid.styles.grid_size_columns = n
            self._page_grid.styles.grid_columns = "1fr"
            self._saved_page_cols = n
            self._persist_layout()
            return
        for view in self._active_views():
            self._set_box_columns(view, n)
        self._saved_group_cols = n
        self._saved_signal_cols = None
        self._persist_layout()

    def _apply_saved_layout(self) -> None:
        """Restore the last-used layout on mount. Group columns set the signal
        density (4-n); a saved signal column then overrides it. Page columns were
        already applied via ``_page_cols`` at compose — re-assert for safety."""
        views = [v for _p, v in self._page_views]
        if self._auto_view is not None:
            views.append(self._auto_view)
        for view in views:
            if self._saved_group_cols != 1:
                self._set_box_columns(view, self._saved_group_cols)
            if self._saved_signal_cols is not None and not view.masonry:
                view.set_columns(self._saved_signal_cols)
        if self._page_grid is not None and self._saved_page_cols != 1:
            self._page_grid.styles.grid_size_columns = self._saved_page_cols
            self._page_grid.styles.grid_columns = "1fr"

    def _persist_layout(self) -> None:
        """Write the current layout choice back to config.toml so it survives a
        restart. No-op without a workspace (e.g. the welcome / no-config case)."""
        if self._workspace is None:
            return
        from pgntui.config import write_layout

        write_layout(
            self._workspace / "config.toml",
            columns=self._saved_signal_cols,
            groups=self._saved_group_cols,
            pages=self._saved_page_cols,
        )

    def action_focus_next_signal(self) -> None:
        self._move_signal_focus(1)

    def action_focus_prev_signal(self) -> None:
        self._move_signal_focus(-1)

    def _move_signal_focus(self, delta: int) -> None:
        widgets: list[Widget] = []
        for view in self._active_views():
            widgets += [
                w for w in view.widgets.values() if isinstance(w, (AnalogInWidget, DigitalInWidget))
            ]
        if not widgets:
            return
        cur = self.focused
        if cur in widgets:
            idx = (widgets.index(cur) + delta) % len(widgets)
        else:
            idx = 0 if delta > 0 else len(widgets) - 1
        widgets[idx].focus()

    def _tick_sparklines(self) -> None:
        for widgets in self._widgets_by_signal.values():
            for w in widgets:
                if isinstance(w, (AnalogInWidget, DigitalInWidget)) and w.expanded:
                    w.tick(self._clock)
                    w.refresh()

    @on(TabbedContent.TabActivated)
    def _on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Track which heavy tab (Debug / Auto) is active and, when one just became
        active, rebuild it from the capped buffer (they aren't fed while hidden)."""
        try:
            active = self.query_one(TabbedContent).active
        except Exception:  # pragma: no cover — pre-mount
            return
        debug_was = self._debug_active
        self._debug_active = active == "debug"
        if self._debug_active and not debug_was:
            self._populate_debug_from_buffer()
        auto_was = self._auto_active
        self._auto_active = active == "tab-auto"
        if self._auto_active and not auto_was:
            self._populate_auto_from_buffer()

    def _populate_auto_from_buffer(self) -> None:
        """Replay the capped DebugBuffer through the Auto builder so opening Auto
        shows the recently-seen PGNs without ingesting frame-by-frame while hidden."""
        if self._auto_builder is None:
            return
        for df in self._debug_buffer.rows():
            self._auto_builder.ingest(df)

    def _populate_debug_from_buffer(self) -> None:
        """Replay the capped DebugBuffer into the log + aggregate so opening Debug
        shows recent history without feeding the views frame-by-frame while hidden."""
        rows = self._debug_buffer.rows()
        if self._debug_log is not None:
            self._debug_log.clear()
            for df in rows:
                self._debug_log.push_decoded(df)
        if self._debug_aggregate is not None:
            self._debug_aggregate.clear_frames()
            for df in rows:
                self._debug_aggregate.push_decoded(df)

    def action_show_debug(self) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = "debug"

    def action_toggle_debug_view(self) -> None:
        """Switch the Debug tab between the streaming trace (default) and the
        aggregated per-PGN monitor. Also brings the Debug tab forward so the
        toggle is visible from any tab.
        """
        if self._debug_log is None or self._debug_aggregate is None:
            return
        self.query_one(TabbedContent).active = "debug"
        show_aggregate = not self._debug_aggregate.display
        self._debug_aggregate.display = show_aggregate
        self._debug_log.display = not show_aggregate
        self._set_status(
            "debug: aggregated (per-PGN)" if show_aggregate else "debug: stream (trace)"
        )

    def _active_views(self) -> list[PageView]:
        """Every PageView under the active tab. The content tab stacks one per
        source page (Nav / Engine / Main sections); Auto has one; Debug none."""
        try:
            active = self.query_one(TabbedContent).active
        except Exception:  # pragma: no cover — pre-mount
            return []
        if active == _CONTENT_TAB_ID:
            return [view for _page, view in self._page_views]
        if active == "tab-auto" and self._auto_view is not None:
            return [self._auto_view]
        return []

    def action_next_instance(self) -> None:
        self._cycle_instance(1)

    def action_prev_instance(self) -> None:
        self._cycle_instance(-1)

    def _cycle_instance(self, delta: int) -> None:
        # Fixed-instance sections (each engine shown at once) don't switch.
        views = [v for v in self._active_views() if v.page.instances and v.fixed_instance is None]
        if not views:
            self._set_status("this page has no instances to switch")
            return
        for view in views:
            view.set_active_instance(view.active_index + delta)
        first = views[0]
        label = first.page.instances[first.active_index].label
        self._set_status(f"showing {label}")

    def action_about(self) -> None:
        # No-op if the About dialog is already open (avoids stacking copies
        # when the key is pressed or the button clicked repeatedly).
        if isinstance(self.screen, AboutScreen):
            return
        self.push_screen(AboutScreen())

    def action_connection(self) -> None:
        if isinstance(self.screen, ConnectionScreen):
            return
        self.push_screen(
            ConnectionScreen(
                workspace=self._workspace,
                current_port=self._driver_options.get("port"),
                current_baud=self._driver_options.get("baud"),
            )
        )

    def action_config(self) -> None:
        if isinstance(self.screen, ConfigScreen):
            return
        self.push_screen(
            ConfigScreen(
                workspace=self._workspace,
                current_theme=self._theme.id,
                themes=list_builtin(),
                info_lines=self._config_info_lines(),
            )
        )

    def _config_info_lines(self) -> list[str]:
        port = self._driver_options.get("port") or "—"
        baud = self._driver_options.get("baud") or "—"
        connected = "yes" if self._n2k_driver is not None else "no"
        writes = "enabled" if self._write_enabled else "disabled"
        return [
            f"Connection: {connected}    Port: {port}    Baud: {baud}",
            f"Writes: {writes}",
            "Use the Connection… button to attach an NGT-1.",
        ]

    def apply_theme(self, theme_id: str) -> None:
        """Switch the active theme live — chrome, CSS classes, and the signal
        widgets — without a restart. No-op on an unknown/invalid theme id.
        """
        try:
            new = load_builtin(theme_id)
        except ThemeLoadError:
            return
        self._theme = new
        textual_theme = to_textual_theme(new)
        self.register_theme(textual_theme)
        self.theme = textual_theme.name
        # Replace the themed-class stylesheet (keyed by the same ``read_from``)
        # so .signal-*, .bar-*, etc. pick up the new colors, then re-apply CSS.
        self.stylesheet.add_source(to_textual_css(new), read_from=("theme", "theme"))
        self.stylesheet.parse()
        self.refresh_css()
        # The signal widgets bake theme colors into their render output, so they
        # need the new theme reference pushed in and a refresh.
        for _page, view in self._page_views:
            view.apply_theme(new)
        if self._auto_view is not None:
            self._auto_view.apply_theme(new)

    def connect_ngt1(self, port: str, baud: int) -> tuple[bool, str]:
        """Open an NGT-1 on ``port`` and start the frame loop. Returns (ok, message).

        Used by the Connection menu's Connect button to go live without a
        restart. Refuses if a driver is already running.
        """
        from pgntui.drivers.actisense import NGT1Driver

        if self._n2k_driver is not None:
            return False, "A driver is already connected — restart pgntui to switch ports."
        if self._decoder is None or self._router is None:
            return False, "No decoder/router available in this session."
        driver = NGT1Driver()
        try:
            driver.open({"port": port, "baud": baud})
        except Exception as e:
            return False, f"Could not open {port}: {e}"
        self._n2k_driver = driver
        self._driver_options = {"port": port, "baud": baud}
        self.frame_loop()
        self._set_status(f"connected {port} @ {baud}")
        return True, f"Connected on {port} @ {baud}. Watch the Debug tab for frames."

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
          2. Close the driver. This is the important one: it sets the driver's
             cooperative ``_stop`` AND releases the serial port / file handle, so
             ``read_frames()`` returns on its next iteration (within the read
             timeout) and the OS port is freed. Cancelling the worker alone does
             NOT do this — a thread worker can't be force-killed, and the read
             loop only checks the driver's own ``_stop``. Skipping the close left
             the loop spinning forever (slow exit) with the port still open.
          3. Cancel the frame-loop worker (belt-and-suspenders; the close above
             already ends the loop) and exit.
        """
        if self._writer is not None:
            try:
                self._stop_recording()
            except Exception:  # pragma: no cover — defensive
                pass
        self._shutdown_driver()
        try:
            for worker in list(self.workers):
                if self._is_frame_loop_worker(worker):
                    worker.cancel()
        except Exception:  # pragma: no cover — defensive
            pass
        self.exit()

    def _shutdown_driver(self) -> None:
        """Close the active driver so its read loop stops and the serial port /
        file handle is released. Safe to call with no driver attached, and
        idempotent (driver.close() may run again from on_unmount)."""
        driver = self._n2k_driver
        if driver is None:
            return
        try:
            driver.close()
        except Exception:  # pragma: no cover — defensive
            pass

    def on_unmount(self) -> None:
        # Safety net: release the driver on ANY exit path, not just force_quit
        # (e.g. ctrl+c, or Textual tearing the app down for another reason).
        self._shutdown_driver()

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


__all__ = [
    "AboutScreen",
    "ConfigScreen",
    "ConnectionScreen",
    "DebugAggregate",
    "DebugLog",
    "MenuScreen",
    "MenuTitle",
    "PgntuiApp",
    "TopBar",
]
