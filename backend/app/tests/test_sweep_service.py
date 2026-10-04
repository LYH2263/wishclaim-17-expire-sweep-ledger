from datetime import datetime, timedelta, timezone

from app.modules.ledger import repo as ledger_repo
from app.modules.sweep import service

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
PAST = (NOW - timedelta(minutes=1)).isoformat()
FUTURE = (NOW + timedelta(hours=1)).isoformat()
T1 = "2020-01-01T00:00:00+00:00"
T2 = "2020-02-02T00:00:00+00:00"


def snapshot(c):
    return [tuple(r) for r in c.execute(
        "SELECT id,status,claimer,claimed_at,expires_at FROM wishes ORDER BY id")]


def ledger_count(c):
    return c.execute("SELECT COUNT(*) n FROM sweep_ledger").fetchone()["n"]


def batch_count(c):
    return c.execute("SELECT COUNT(*) n FROM sweep_batches").fetchone()["n"]


def prepare_four_states(c):
    """id1 open, id2 claimed unexpired, id4 claimed expired, id3 released."""
    c.execute("UPDATE wishes SET status='open',claimer=NULL,claimed_at=NULL,expires_at=NULL")
    c.execute("UPDATE wishes SET status='claimed',claimer=?,claimed_at=?,expires_at=? WHERE id=2",
              ("bob", T1, FUTURE))
    c.execute("UPDATE wishes SET status='released',claimer=NULL,claimed_at=NULL,expires_at=NULL WHERE id=3")
    c.execute("UPDATE wishes SET status='claimed',claimer=?,claimed_at=?,expires_at=? WHERE id=4",
              ("ghost", T1, PAST))
    c.commit()


def test_dry_run_lists_only_expired_and_writes_nothing(db):
    prepare_four_states(db)
    before = snapshot(db)
    res = service.dry_run(db, NOW)
    assert res["count"] == 1
    assert res["candidates"] == [{
        "wish_id": 4, "claimer": "ghost", "claimed_at": T1, "expires_at": PAST,
    }]
    assert snapshot(db) == before
    assert ledger_count(db) == 0 and batch_count(db) == 0


def test_commit_releases_only_expired_and_books_ledger(db):
    prepare_four_states(db)
    res = service.commit_sweep(db, NOW)
    assert res["batch_id"] is not None
    assert res["released_count"] == 1 and res["skipped_count"] == 0
    assert res["released"] == [{"wish_id": 4, "claimer": "ghost"}]

    rows = {r["id"]: r for r in db.execute("SELECT * FROM wishes ORDER BY id")}
    assert rows[4]["status"] == "open"
    assert rows[4]["claimer"] is None
    assert rows[4]["claimed_at"] is None and rows[4]["expires_at"] is None
    assert rows[1]["status"] == "open"
    assert rows[2]["status"] == "claimed" and rows[2]["claimer"] == "bob"
    assert rows[3]["status"] == "released"

    entries = ledger_repo.entries_for_wish(db, 4)
    assert len(entries) == 1
    e = entries[0]
    assert e["claimer"] == "ghost" and e["at"] == NOW.isoformat()
    assert e["batch_id"] == res["batch_id"] and e["source"] == "sweep"
    assert ledger_count(db) == 1
    batch = ledger_repo.get_batch(db, res["batch_id"])
    assert batch["candidate_count"] == 1
    assert batch["released_count"] == 1 and batch["skipped_count"] == 0


def test_commit_twice_is_idempotent(db):
    prepare_four_states(db)
    first = service.commit_sweep(db, NOW)
    assert first["released_count"] == 1
    second = service.commit_sweep(db, NOW)
    assert second["batch_id"] is None
    assert second["released"] == [] and second["released_count"] == 0
    assert ledger_count(db) == 1 and batch_count(db) == 1


def test_new_lock_incarnation_can_be_booked_again(db):
    prepare_four_states(db)
    first = service.commit_sweep(db, NOW)

    # Same wish claimed again later, new lock expires again.
    later = NOW + timedelta(days=1)
    db.execute("UPDATE wishes SET status='claimed',claimer=?,claimed_at=?,expires_at=? WHERE id=4",
               ("carol", T2, (later - timedelta(minutes=1)).isoformat()))
    # Keep id2's lock unexpired relative to the later commit time.
    db.execute("UPDATE wishes SET expires_at=? WHERE id=2",
               ((later + timedelta(hours=1)).isoformat(),))
    db.commit()
    second = service.commit_sweep(db, later)
    assert second["batch_id"] is not None and second["batch_id"] != first["batch_id"]
    assert ledger_count(db) == 2
    keys = [r["lock_key"] for r in db.execute("SELECT lock_key FROM sweep_ledger ORDER BY id")]
    assert keys[0] != keys[1]
    assert keys == [f"4:{T1}", f"4:{T2}"]


def test_dry_run_and_commit_candidate_sets_match(db):
    prepare_four_states(db)
    previewed = {x["wish_id"] for x in service.select_candidates(db, NOW)}
    res = service.commit_sweep(db, NOW)
    committed = {x["wish_id"] for x in res["released"]} | {x["wish_id"] for x in res["skipped"]}
    assert previewed == committed == {4}


def test_commit_skips_row_manually_released_after_dry_run(db, monkeypatch):
    prepare_four_states(db)
    stale = service.select_candidates(db, NOW)
    assert [x["wish_id"] for x in stale] == [4]
    # Rival manual release interleaves between candidate SELECT and UPDATE.
    db.execute("UPDATE wishes SET status='released',claimer=NULL,claimed_at=NULL,expires_at=NULL WHERE id=4")
    db.commit()
    monkeypatch.setattr(service, "select_candidates", lambda *a, **k: stale)
    res = service.commit_sweep(db, NOW)
    assert res["released"] == []
    assert res["skipped"] == [{"wish_id": 4, "reason": "changed"}]
    assert db.execute("SELECT status FROM wishes WHERE id=4").fetchone()["status"] == "released"
    assert ledger_count(db) == 0
    assert res["batch_id"] is None


def test_commit_skips_row_reclaimed_with_new_lock(db, monkeypatch):
    prepare_four_states(db)
    stale = service.select_candidates(db, NOW)
    # Someone else grabs it with a fresh (unexpired) lock before the UPDATE.
    db.execute("UPDATE wishes SET claimer=?,claimed_at=?,expires_at=? WHERE id=4",
               ("carol", T2, FUTURE))
    db.commit()
    monkeypatch.setattr(service, "select_candidates", lambda *a, **k: stale)
    res = service.commit_sweep(db, NOW)
    assert res["released"] == []
    assert [s["wish_id"] for s in res["skipped"]] == [4]
    row = db.execute("SELECT * FROM wishes WHERE id=4").fetchone()
    assert row["status"] == "claimed" and row["claimer"] == "carol"
    assert ledger_count(db) == 0


def test_commit_one_of_two_releases_other_on_race(db, monkeypatch):
    prepare_four_states(db)
    # Add a second expired lock (id2: change its expiry to the past).
    db.execute("UPDATE wishes SET expires_at=? WHERE id=2", (PAST,))
    db.commit()
    stale = service.select_candidates(db, NOW)
    assert [x["wish_id"] for x in stale] == [2, 4]
    # id4 manually released while id2 still expired.
    db.execute("UPDATE wishes SET status='released',claimer=NULL,claimed_at=NULL,expires_at=NULL WHERE id=4")
    db.commit()
    monkeypatch.setattr(service, "select_candidates", lambda *a, **k: stale)
    res = service.commit_sweep(db, NOW)
    assert res["released"] == [{"wish_id": 2, "claimer": "bob"}]
    assert res["skipped"] == [{"wish_id": 4, "reason": "changed"}]
    assert ledger_count(db) == 1
    assert ledger_repo.entries_for_wish(db, 4) == []
    assert len(ledger_repo.entries_for_wish(db, 2)) == 1
    assert db.execute("SELECT status FROM wishes WHERE id=4").fetchone()["status"] == "released"


def test_insert_ledger_entries_ignores_duplicate_lock_key(db):
    from app.modules.ledger.engine import make_lock_key
    # Pre-book the ghost lock, then reset the wish to the same incarnation
    # (defensive layer: INSERT OR IGNORE must not double-book).
    now_s = NOW.isoformat()
    db.execute("INSERT INTO sweep_batches(batch_id,source,created_at,candidate_count,"
               "released_count,skipped_count) VALUES ('BOLD','sweep',?,1,1,0)", (now_s,))
    db.execute("INSERT INTO sweep_ledger(batch_id,wish_id,claimer,claimed_at,released_at,lock_key)"
               " VALUES ('BOLD',4,'ghost',?,?,?)", (T1, now_s, make_lock_key(4, T1)))
    db.commit()
    n = ledger_repo.insert_ledger_entries(
        db, "BNEW", now_s, [{"wish_id": 4, "claimer": "ghost", "claimed_at": T1}])
    assert n == 0
    assert ledger_count(db) == 1
