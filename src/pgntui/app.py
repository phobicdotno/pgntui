"""Textual app shell — tabs, hotkey strip, status bar."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, TabbedContent, TabPane

from pgntui.themes.loader import Theme, to_textual_css


class PgntuiApp(App):
    CSS = ""

    BINDINGS = [
        ("tab", "next_container", "Next"),
        ("shift+tab", "prev_container", "Prev"),
        ("d", "show_debug", "Debug"),
        ("r", "toggle_record", "Record"),
        ("q", "quit", "Quit"),
        ("question_mark", "help", "Help"),
    ]

    def __init__(self, theme: Theme, container_titles: list[str]) -> None:
        super().__init__()
        self._theme = theme
        self._container_titles = container_titles

    def on_mount(self) -> None:
        self.stylesheet.add_source(to_textual_css(self._theme), read_from=("theme", "theme"))
        self.stylesheet.parse()
        self.refresh_css()

    def compose(self) -> ComposeResult:
        with Vertical():
            with TabbedContent(id="tabs"):
                for title in self._container_titles:
                    with TabPane(title):
                        yield Static(title, classes="signal-title")
                with TabPane("Debug"):
                    yield Static("debug placeholder")
            yield Static("[Tab] Next [D] Debug [R] Rec [Q] Quit", id="hotkey-strip")
            yield Static("status: idle", id="status-bar")

    def action_next_container(self) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.action_next_tab()

    def action_prev_container(self) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.action_previous_tab()

    def action_show_debug(self) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = "tab-" + str(len(self._container_titles) + 1)

    def action_toggle_record(self) -> None:
        status = self.query_one("#status-bar", Static)
        status.update("status: REC")

    def action_help(self) -> None:
        status = self.query_one("#status-bar", Static)
        status.update("help: Tab/D/R/Q")


__all__ = ["PgntuiApp"]
