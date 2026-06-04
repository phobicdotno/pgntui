from pgntui.drivers.base import Capability, Frame


def test_frame_construct_and_repr() -> None:
    f = Frame(timestamp=1.5, source_addr=23, pgn=127488, data=b"\x01\x02\x03")
    assert f.timestamp == 1.5
    assert f.source_addr == 23
    assert f.pgn == 127488
    assert f.data == b"\x01\x02\x03"


def test_frame_is_immutable() -> None:
    import dataclasses

    f = Frame(timestamp=0.0, source_addr=0, pgn=0, data=b"")
    try:
        f.pgn = 1  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("Frame must be frozen")


def test_capability_values() -> None:
    assert {Capability.READ, Capability.WRITE, Capability.REPLAY} == set(Capability)


def test_driver_protocol_runtime_checkable() -> None:
    from pgntui.drivers.base import Driver

    class Dummy:
        name = "dummy"
        capabilities = {Capability.READ}

        def open(self, config: dict) -> None: ...
        def close(self) -> None: ...
        def read_frames(self):
            yield from ()

        def write_frame(self, frame: Frame) -> None: ...

    assert isinstance(Dummy(), Driver)
