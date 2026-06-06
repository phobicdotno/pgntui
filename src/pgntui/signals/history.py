"""Time-bucketed sample history for sparklines.

Pure data — no Textual, no glyphs — so it unit-tests in isolation. Each sample
is assigned to a fixed wall-clock bucket (``int(ts // bucket_seconds)``); the
last value written to a bucket wins. ``columns`` projects the stored buckets
onto a fixed-width window ending at "now", with ``None`` for buckets that never
received a sample (gaps), so a stopped signal scrolls left into trailing gaps.
"""

from __future__ import annotations


class History:
    def __init__(self, bucket_seconds: float = 1.0, capacity: int = 300) -> None:
        if bucket_seconds <= 0:
            raise ValueError("bucket_seconds must be > 0")
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.bucket_seconds = bucket_seconds
        self.capacity = capacity
        # Insertion-ordered (dict preserves order); key = bucket index, value =
        # last sample in that bucket. Re-writing a key keeps its position, so the
        # front is always the oldest bucket.
        self._buckets: dict[int, float] = {}

    def add(self, value: float, ts: float) -> None:
        idx = int(ts // self.bucket_seconds)
        self._buckets[idx] = float(value)
        while len(self._buckets) > self.capacity:
            oldest = next(iter(self._buckets))
            del self._buckets[oldest]

    def columns(self, now: float, width: int) -> list[float | None]:
        if width <= 0:
            return []
        now_idx = int(now // self.bucket_seconds)
        start = now_idx - (width - 1)
        return [self._buckets.get(start + i) for i in range(width)]

    def clear(self) -> None:
        self._buckets.clear()

    def __len__(self) -> int:
        return len(self._buckets)


__all__ = ["History"]
