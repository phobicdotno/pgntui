"""Driver selection at launch (no UI)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from pgntui.__main__ import main
from pgntui.app import PgntuiApp


def test_default_file_replay_starts_with_no_driver_and_no_warning(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    """The scaffold's placeholder file-replay driver (no path) must not be
    opened at launch — doing so printed 'failed to open driver: path'."""
    ws = tmp_path / "ws"
    assert main(["--workspace", str(ws), "--example"]) == 0
    capsys.readouterr()  # drop the scaffold message

    captured: dict[str, Any] = {}

    def fake_run(self: PgntuiApp, *_a: object, **_k: object) -> None:
        captured["driver"] = self._n2k_driver

    with patch.object(PgntuiApp, "run", fake_run):
        rc = main(["--workspace", str(ws)])

    assert rc == 0
    assert captured["driver"] is None
    err = capsys.readouterr().err
    assert "failed to open driver" not in err
