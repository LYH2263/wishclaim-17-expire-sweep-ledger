from datetime import datetime, timedelta, timezone

from app.modules.ledger import repo as ledger_repo
from app.modules.projections import detail, wall
from app.modules.sweep import service

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
PAST = (NOW - timedelta(minutes=1)).isoformat()
T1 = "2020-01-01T00:00:00+00:00"


def _expire_seed_lock(db):
    db.execute("UPDATE wishes SET status='claimed',claimer='ghost',claimed_at=?,expires_at=? WHERE id=4",
               (T1, PAST))
    db.commit()


def snapshot(db):
    return [tuple(r) for r in db.execute(
        "SELECT id,status,claimer,claimed_at,expires_at FROM wishes ORDER BY id")]


def test_wall_projection_flags_eligibility_without_writing(db):
    _expire_seed_lock(db)
    before = snapshot(db)
    rows = wall.list_wishes(db, NOW)
    by_id = {r["id"]: r for r in rows}
    assert by_id[4]["sweep_eligible"] is True
    assert by_id[1]["sweep_eligible"] is False
    assert "sweep_eligible" in by_id[2]
    assert snapshot(db) == before


def test_events_empty_before_commit_and_pinned_after(db):
    assert detail.events_for_wish(db, 4) == []
    res = service.commit_sweep(db, NOW)
    events = detail.events_for_wish(db, 4)
    assert len(events) == 1
    e = events[0]
    assert e["type"] == "sweep_release"
    assert e["claimer"] == "ghost"
    assert e["batch_id"] == res["batch_id"]
    assert e["source"] == "sweep"


def test_reclaim_commit_flags_source_reclaim(db):
    _expire_seed_lock(db)
    res = service.commit_sweep(db, NOW, source="reclaim", wish_id=4, commit=False)
    db.commit()
    e = detail.events_for_wish(db, 4)[0]
    assert e["source"] == "reclaim"
    assert e["batch_id"] == res["batch_id"]


def test_ledger_listing_groups_entries_with_title(db):
    _expire_seed_lock(db)
    res = service.commit_sweep(db, NOW)
    batches = ledger_repo.list_batches_with_entries(db)
    assert len(batches) == 1
    b = batches[0]
    assert b["batch_id"] == res["batch_id"]
    assert b["released_count"] == 1
    assert b["entries"][0]["wish_id"] == 4
    assert b["entries"][0]["title"] == "过期锁样例"
    assert b["entries"][0]["claimer"] == "ghost"

    fetched = ledger_repo.get_batch(db, res["batch_id"])
    assert fetched["entries"][0]["title"] == "过期锁样例"
    assert ledger_repo.get_batch(db, "nope") is None
