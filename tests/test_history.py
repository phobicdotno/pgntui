from pgntui.signals.history import History


def test_add_buckets_by_timestamp_last_wins() -> None:
    h = History(bucket_seconds=1.0, capacity=10)
    h.add(1.0, ts=0.1)
    h.add(2.0, ts=0.9)  # same 1 s bucket as 0.1 -> overwrites
    h.add(5.0, ts=1.2)  # next bucket
    assert h.columns(now=1.2, width=2) == [2.0, 5.0]


def test_columns_right_edge_is_now_and_gaps_are_none() -> None:
    h = History(bucket_seconds=1.0, capacity=10)
    h.add(3.0, ts=0.0)   # bucket 0
    h.add(7.0, ts=2.0)   # bucket 2  (bucket 1 never written -> gap)
    assert h.columns(now=2.5, width=3) == [3.0, None, 7.0]
    assert h.columns(now=4.5, width=3) == [7.0, None, None]


def test_columns_zero_or_negative_width() -> None:
    h = History()
    assert h.columns(now=0.0, width=0) == []


def test_eviction_drops_oldest_beyond_capacity() -> None:
    h = History(bucket_seconds=1.0, capacity=3)
    for i in range(5):
        h.add(float(i), ts=float(i))  # buckets 0..4
    assert len(h) == 3
    assert h.columns(now=4.0, width=5) == [None, None, 2.0, 3.0, 4.0]


def test_clear_empties() -> None:
    h = History()
    h.add(1.0, ts=0.0)
    h.clear()
    assert len(h) == 0
    assert h.columns(now=0.0, width=2) == [None, None]


def test_rejects_bad_params() -> None:
    import pytest

    with pytest.raises(ValueError):
        History(bucket_seconds=0)
    with pytest.raises(ValueError):
        History(capacity=0)
