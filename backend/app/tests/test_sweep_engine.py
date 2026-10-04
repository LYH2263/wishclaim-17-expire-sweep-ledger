from datetime import datetime, timedelta, timezone

from app.modules.ledger.engine import make_lock_key, new_batch_id
from app.modules.sweep.engine import candidate_from_row, is_expired_lock

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


class Row:
    """Minimal sqlite3.Row-like object for engine tests."""
    def __init__(self, d): self._d = d
    def __getitem__(self, k): return self._d[k]


def test_is_expired_lock_states():
    past = (NOW - timedelta(minutes=1)).isoformat()
    future = (NOW + timedelta(minutes=1)).isoformat()
    assert is_expired_lock("claimed", past, NOW) is True
    assert is_expired_lock("claimed", future, NOW) is False
    assert is_expired_lock("open", past, NOW) is False
    assert is_expired_lock("released", past, NOW) is False
    assert is_expired_lock("claimed", None, NOW) is False


def test_candidate_from_row_carries_lock_version():
    past = (NOW - timedelta(minutes=1)).isoformat()
    cand = candidate_from_row(Row({
        "id": 9, "status": "claimed", "claimer": "ghost",
        "claimed_at": "2020-01-01T00:00:00+00:00", "expires_at": past,
    }), NOW)
    assert cand == {
        "wish_id": 9, "claimer": "ghost",
        "claimed_at": "2020-01-01T00:00:00+00:00", "expires_at": past,
    }
    assert candidate_from_row(Row({
        "id": 9, "status": "open", "claimer": None,
        "claimed_at": None, "expires_at": None,
    }), NOW) is None


def test_lock_key_distinguishes_incarnations():
    t1, t2 = "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"
    assert make_lock_key(1, t1) != make_lock_key(1, t2)
    assert make_lock_key(1, t1) == make_lock_key(1, t1)
    assert make_lock_key(1, t1) != make_lock_key(2, t1)


def test_new_batch_id_format():
    bid = new_batch_id(NOW, "abcdef0123456789")
    assert bid == "B20260101T120000000000-abcdef01"
