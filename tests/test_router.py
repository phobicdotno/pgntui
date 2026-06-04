from pgntui.decode.canboat import DecodedFrame
from pgntui.decode.router import SignalKey, SignalRouter, SignalUpdate


def test_router_matches_pgn_field_source_instance() -> None:
    router = SignalRouter()
    router.bind("rpm_port", SignalKey(pgn=127488, field="Engine Speed", source=23, instance=0))
    df = DecodedFrame(
        timestamp=1.0,
        source_addr=23,
        pgn=127488,
        name="Engine",
        fields={"Engine Speed": 2150.0, "Instance": 0},
    )
    updates = list(router.route(df))
    assert updates == [SignalUpdate(signal_id="rpm_port", timestamp=1.0, value=2150.0)]


def test_router_skips_non_matching_source() -> None:
    router = SignalRouter()
    router.bind("rpm_port", SignalKey(pgn=127488, field="Engine Speed", source=23, instance=0))
    df = DecodedFrame(
        timestamp=1.0,
        source_addr=99,
        pgn=127488,
        name="Engine",
        fields={"Engine Speed": 2150.0, "Instance": 0},
    )
    assert list(router.route(df)) == []


def test_router_multi_source_distinct_signals() -> None:
    router = SignalRouter()
    router.bind("rpm_port", SignalKey(pgn=127488, field="Engine Speed", source=23, instance=0))
    router.bind("rpm_stbd", SignalKey(pgn=127488, field="Engine Speed", source=35, instance=1))
    df1 = DecodedFrame(1.0, 23, 127488, "Engine", {"Engine Speed": 2100.0, "Instance": 0})
    df2 = DecodedFrame(1.0, 35, 127488, "Engine", {"Engine Speed": 2200.0, "Instance": 1})
    ids = [u.signal_id for u in list(router.route(df1)) + list(router.route(df2))]
    assert ids == ["rpm_port", "rpm_stbd"]


def test_router_source_none_is_wildcard() -> None:
    router = SignalRouter()
    router.bind("rpm_any", SignalKey(pgn=127488, field="Engine Speed", source=None, instance=None))
    df = DecodedFrame(1.0, 99, 127488, "Engine", {"Engine Speed": 2100.0, "Instance": 7})
    assert [u.signal_id for u in router.route(df)] == ["rpm_any"]
