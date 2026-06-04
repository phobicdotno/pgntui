import threading
import time
from pathlib import Path

import pytest

from pgntui.drivers.replay import FileReplayDriver
from pgntui.replay_mode import SPEED_LADDER, ReplaySession

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pgnlog"


def test_speed_cycle() -> None:
    s = ReplaySession(path=FIXTURE)
    start = s.speed
    assert start in SPEED_LADDER
    s.cycle_speed()
    assert s.speed != start


def test_writes_disabled() -> None:
    s = ReplaySession(path=FIXTURE)
    assert s.write_enabled is False


def test_iterates_through_file() -> None:
    s = ReplaySession(path=FIXTURE, speed="max")
    driver = s.driver
    assert isinstance(driver, FileReplayDriver)
    s.open()
    frames = list(s.iter_frames())
    s.close()
    assert len(frames) == 3


def test_pause_resume_state() -> None:
    s = ReplaySession(path=FIXTURE)
    assert not s.paused
    s.toggle_pause()
    assert s.paused
    s.toggle_pause()
    assert not s.paused


def _write_three_frame_fixture(path: Path, spacing_ms: int = 100) -> None:
    """Write a .pgnlog fixture with 3 frames at fixed spacing."""
    # Base timestamp arbitrary; only deltas matter for the replay loop.
    base_s = 0  # seconds within minute
    lines = []
    for i in range(3):
        total_ms = base_s * 1000 + i * spacing_ms
        sec = total_ms // 1000
        ms = total_ms % 1000
        ts = f"2026-06-04-15:42:{sec:02d}.{ms:03d}"
        lines.append(f"{ts},2,127488,23,255,8,00,98,21,0c,00,00,ff,ff")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_iter_frames_honors_pause_with_sliding_resume(tmp_path: Path) -> None:
    """Pausing must halt frame emission; resuming continues without catching up."""
    fixture = tmp_path / "paused.pgnlog"
    # 200ms spacing leaves a meaningful inter-frame window even after the
    # ~50ms pause-poll quantum eats into the first half of the dt sleep.
    spacing_ms = 200
    _write_three_frame_fixture(fixture, spacing_ms=spacing_ms)

    s = ReplaySession(path=fixture, speed="1x")
    s.open()

    emitted: list[float] = []  # wall-clock time of each emitted frame
    done = threading.Event()

    def consume() -> None:
        try:
            for _frame in s.iter_frames():
                emitted.append(time.monotonic())
        finally:
            done.set()

    t = threading.Thread(target=consume, daemon=True)
    t.start()

    # Wait for the first frame to land (no inter-frame delay before frame 0).
    deadline = time.monotonic() + 2.0
    while len(emitted) < 1 and time.monotonic() < deadline:
        time.sleep(0.005)
    assert len(emitted) == 1, "first frame should arrive immediately"

    # Pause immediately; the inter-frame sleep before frame 2 is in progress.
    # Frames 2 (+200ms) and 3 (+400ms) would normally land within the next
    # ~400ms. Sleep through that window and confirm neither arrives.
    s.toggle_pause()
    time.sleep(0.6)
    assert len(emitted) == 1, f"no frames should be emitted while paused; got {len(emitted)}"

    # Resume — frame 2 should arrive after the leftover inter-frame delay
    # (sliding semantics), not instantly (which would mean catching up the
    # wall-clock time we slept while paused).
    resume_at = time.monotonic()
    s.toggle_pause()

    deadline = resume_at + 3.0
    while len(emitted) < 3 and time.monotonic() < deadline:
        time.sleep(0.005)
    done.wait(timeout=3.0)
    s.close()

    assert len(emitted) == 3, f"expected all 3 frames after resume; got {len(emitted)}"

    # Sliding check: frame 2 must not have fired immediately on resume — if
    # the driver were catching up, the dt sleep would already be satisfied.
    # We require at least 25ms (one poll quantum minus jitter) of post-resume
    # delay; an instant fire would be < 5ms.
    delay_after_resume = emitted[1] - resume_at
    assert delay_after_resume >= 0.025, (
        f"frame 2 fired {delay_after_resume * 1000:.1f}ms after resume — "
        "looks like catching up, not sliding"
    )


def test_set_paused_propagates_from_session() -> None:
    """ReplaySession.toggle_pause must propagate to the underlying driver."""
    s = ReplaySession(path=FIXTURE)
    driver = s.driver
    assert isinstance(driver, FileReplayDriver)
    assert driver._paused is False
    s.toggle_pause()
    assert driver._paused is True
    s.toggle_pause()
    assert driver._paused is False


# Silence "unused import" for pytest in environments without pytest-asyncio enabled
_ = pytest
