"""Signal router — matches decoded frames to user-bound signal ids."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from pgntui.decode.canboat import DecodedFrame


@dataclass(frozen=True, slots=True)
class SignalKey:
    pgn: int
    field: str
    source: int | None = None
    instance: int | None = None


@dataclass(frozen=True, slots=True)
class SignalUpdate:
    signal_id: str
    timestamp: float
    value: object


class SignalRouter:
    def __init__(self) -> None:
        self._by_pgn: dict[int, list[tuple[str, SignalKey]]] = {}

    def bind(self, signal_id: str, key: SignalKey) -> None:
        self._by_pgn.setdefault(key.pgn, []).append((signal_id, key))

    def route(self, df: DecodedFrame) -> Iterator[SignalUpdate]:
        bindings = self._by_pgn.get(df.pgn)
        if not bindings:
            return
        instance = df.fields.get("Instance")
        for signal_id, key in bindings:
            if key.source is not None and key.source != df.source_addr:
                continue
            if key.instance is not None and instance is not None and key.instance != instance:
                continue
            if key.field not in df.fields:
                continue
            yield SignalUpdate(
                signal_id=signal_id,
                timestamp=df.timestamp,
                value=df.fields[key.field],
            )


__all__ = ["SignalKey", "SignalRouter", "SignalUpdate"]
