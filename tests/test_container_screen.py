import pytest

from pgntui.containers.loader import Container, SignalPlacement
from pgntui.containers.screen import ContainerScreen
from pgntui.signals.base import AnalogIn


def _sigs() -> dict:
    return {
        "rpm_port": AnalogIn(id="rpm_port", type="analog_in", title="Port RPM",
            pgn=127488, field="Engine Speed", min=0, max=6000),
        "rpm_stbd": AnalogIn(id="rpm_stbd", type="analog_in", title="Stbd RPM",
            pgn=127488, field="Engine Speed", min=0, max=6000),
    }


@pytest.mark.asyncio
async def test_screen_mounts_one_widget_per_placement() -> None:
    c = Container(id="er", title="ER", cols=12, signals=[
        SignalPlacement(ref="rpm_port", row=0, col=0, w=12),
        SignalPlacement(ref="rpm_stbd", row=1, col=0, w=12),
    ])
    screen = ContainerScreen(container=c, signals=_sigs(), write_enabled=False)
    from textual.app import App

    class Host(App):
        def on_mount(self):
            self.push_screen(screen)

    app = Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(list(screen.widgets.values())) == 2
