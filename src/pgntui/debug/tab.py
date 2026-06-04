"""Debug tab — scrolling decoded-frame buffer with filters."""

from __future__ import annotations

from collections import deque

from pgntui.decode.canboat import DecodedFrame


class DebugBuffer:
    def __init__(
        self,
        max_rows: int = 1000,
        pgn_filter: set[int] | None = None,
        source_filter: set[int] | None = None,
        show_raw_hex: bool = False,
    ) -> None:
        self._rows: deque[DecodedFrame] = deque(maxlen=max_rows)
        self.paused = False
        self.pgn_filter = pgn_filter
        self.source_filter = source_filter
        self.show_raw_hex = show_raw_hex

    def push(self, df: DecodedFrame) -> None:
        if self.paused:
            return
        if self.pgn_filter is not None and df.pgn not in self.pgn_filter:
            return
        if self.source_filter is not None and df.source_addr not in self.source_filter:
            return
        self._rows.append(df)

    def rows(self) -> list[DecodedFrame]:
        return list(self._rows)

    def clear(self) -> None:
        self._rows.clear()

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def toggle_raw_hex(self) -> None:
        self.show_raw_hex = not self.show_raw_hex


__all__ = ["DebugBuffer"]
