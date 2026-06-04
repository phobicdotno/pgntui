import pytest

from pgntui.containers.loader import Container, SignalPlacement
from pgntui.containers.screen import ContainerScreen
from pgntui.signals.base import AnalogIn
from pgntui.signals.widgets import AnalogInWidget


def _sigs() -> dict:
    return {
        "rpm_port": AnalogIn(
            id="rpm_port",
            type="analog_in",
            title="Port RPM",
            pgn=127488,
            field="Engine Speed",
            min=0,
            max=6000,
        ),
        "rpm_stbd": AnalogIn(
            id="rpm_stbd",
            type="analog_in",
            title="Stbd RPM",
            pgn=127488,
            field="Engine Speed",
            min=0,
            max=6000,
        ),
    }


@pytest.mark.asyncio
async def test_screen_mounts_one_widget_per_placement() -> None:
    c = Container(
        id="er",
        title="ER",
        cols=12,
        signals=[
            SignalPlacement(ref="rpm_port", row=0, col=0, w=12),
            SignalPlacement(ref="rpm_stbd", row=1, col=0, w=12),
        ],
    )
    screen = ContainerScreen(container=c, signals=_sigs(), write_enabled=False)
    from textual.app import App

    class Host(App):
        def on_mount(self):
            self.push_screen(screen)

    app = Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(list(screen.widgets.values())) == 2


@pytest.mark.asyncio
async def test_screen_applies_column_span_after_mount() -> None:
    """Regression: ``column_span`` must be set AFTER the widget is mounted.

    Previously ``compose`` assigned ``w.styles.column_span = placement.w``
    on a bare widget that had not yet been attached to the DOM. Textual
    silently discards style writes in that state, so the placement width
    was lost and every cell rendered with the default span of 1.
    """
    c = Container(
        id="er",
        title="ER",
        cols=12,
        signals=[
            SignalPlacement(ref="rpm_port", row=0, col=0, w=4),
            SignalPlacement(ref="rpm_stbd", row=0, col=4, w=8),
        ],
    )
    screen = ContainerScreen(container=c, signals=_sigs(), write_enabled=False)
    from textual.app import App

    class Host(App):
        def on_mount(self):
            self.push_screen(screen)

    app = Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert screen.widgets["rpm_port"].styles.column_span == 4
        assert screen.widgets["rpm_stbd"].styles.column_span == 8
        # widgets dict round-trips to the actual mounted widgets
        assert isinstance(screen.widgets["rpm_port"], AnalogInWidget)
        assert isinstance(screen.widgets["rpm_stbd"], AnalogInWidget)
        assert screen.widgets["rpm_port"].signal.id == "rpm_port"
        assert screen.widgets["rpm_stbd"].signal.id == "rpm_stbd"
        # Both widgets are actually attached to the screen's DOM
        assert screen.widgets["rpm_port"].is_mounted
        assert screen.widgets["rpm_stbd"].is_mounted
