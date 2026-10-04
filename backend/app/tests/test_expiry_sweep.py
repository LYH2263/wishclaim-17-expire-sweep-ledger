from datetime import datetime, timedelta, timezone
import sqlite3

from app.modules import expiry_sweep, release_ledger

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        "CREATE TABLE wishes("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, note TEXT, status TEXT,"
        "claimer TEXT, claimed_at TEXT, expires_at TEXT, data_quality TEXT)"
    )
    release_ledger.ensure_schema(c)
    return c


def add(c, status, claimer, claimed_at, expires_at):
    c.execute(
        "INSERT INTO wishes(title,note,status,claimer,claimed_at,expires_at,data_quality)"
        " VALUES (?,?,?,?,?,?,?)",
        ("t", "n", status, claimer, claimed_at, expires_at, "clean"),
    )
    return c.execute("SELECT last_insert_rowid() i").fetchone()["i"]


EXPIRED_TS = (NOW - timedelta(hours=1)).isoformat()
FUTURE_TS = (NOW + timedelta(hours=1)).isoformat()
CLAIMED_TS = (NOW - timedelta(days=2)).isoformat()


def setup_mixed(c):
    expired = add(c, "claimed", "ghost", CLAIMED_TS, EXPIRED_TS)
    open_w = add(c, "open", None, None, None)
    fresh = add(c, "claimed", "bob", CLAIMED_TS, FUTURE_TS)
    manual = add(c, "claimed", "carol", CLAIMED_TS, EXPIRED_TS)
    c.execute("UPDATE wishes SET status='released', claimer=NULL, claimed_at=NULL, expires_at=NULL WHERE id=?", (manual,))
    c.commit()
    return expired, open_w, fresh, manual


def test_dry_run_readonly_lists_wish_and_claimer():
    c = db()
    expired, open_w, fresh, manual = setup_mixed(c)

    found = expiry_sweep.dry_run(c, NOW)
    assert [(x["wish_id"], x["claimer"]) for x in found] == [(expired, "ghost")]

    # wishes untouched
    row = c.execute("SELECT * FROM wishes WHERE id=?", (expired,)).fetchone()
    assert row["status"] == "claimed" and row["claimer"] == "ghost"
    # nothing ledgered
    assert release_ledger.list_rows(c) == []


def test_commit_releases_and_appends_ledger():
    c = db()
    expired, _, _, _ = setup_mixed(c)

    result = expiry_sweep.commit(c, NOW)
    assert result["ledgered"] == 1
    entry = result["released"][0]
    assert entry["wish_id"] == expired and entry["claimer"] == "ghost"
    assert result["batch_id"].startswith("sweep-")

    row = c.execute("SELECT * FROM wishes WHERE id=?", (expired,)).fetchone()
    assert row["status"] == "open" and row["claimer"] is None

    ledger = release_ledger.list_rows(c)
    assert len(ledger) == 1
    assert ledger[0]["wish_id"] == expired
    assert ledger[0]["claimer"] == "ghost"
    assert ledger[0]["batch_id"] == result["batch_id"]
    assert ledger[0]["released_at"]


def test_double_commit_does_not_double_count():
    c = db()
    setup_mixed(c)

    first = expiry_sweep.commit(c, NOW)
    second = expiry_sweep.commit(c, NOW)
    assert first["ledgered"] == 1
    assert second["ledgered"] == 0 and second["batch_id"] is None
    assert len(release_ledger.list_rows(c)) == 1


def test_open_unexpired_manually_released_never_ledgered():
    c = db()
    expired, open_w, fresh, manual = setup_mixed(c)
    expiry_sweep.commit(c, NOW)
    ids = {r["wish_id"] for r in release_ledger.list_rows(c)}
    assert ids == {expired}
    assert open_w not in ids and fresh not in ids and manual not in ids
    # manually released row stays released, untouched
    row = c.execute("SELECT status FROM wishes WHERE id=?", (manual,)).fetchone()
    assert row["status"] == "released"


def test_dry_run_and_commit_candidate_sets_match():
    c = db()
    setup_mixed(c)
    dry = {x["wish_id"] for x in expiry_sweep.dry_run(c, NOW)}
    result = expiry_sweep.commit(c, NOW)
    committed = {x["wish_id"] for x in result["released"]}
    assert dry == committed


def test_manual_release_between_dryrun_and_commit_excludes_row():
    c = db()
    expired, _, _, _ = setup_mixed(c)
    dry = expiry_sweep.dry_run(c, NOW)
    assert [x["wish_id"] for x in dry] == [expired]

    # someone manually releases before commit
    c.execute(
        "UPDATE wishes SET status='released', claimer=NULL, claimed_at=NULL, expires_at=NULL WHERE id=?",
        (expired,),
    )
    c.commit()
    result = expiry_sweep.commit(c, NOW)
    assert result["ledgered"] == 0
    assert release_ledger.list_rows(c) == []


def test_reclaim_after_sweep_gets_own_ledger_row():
    c = db()
    expired, _, _, _ = setup_mixed(c)
    first = expiry_sweep.commit(c, NOW)
    # re-claim with a new lock that later expires again
    second_claim_ts = (NOW + timedelta(days=1)).isoformat()
    second_exp = (NOW + timedelta(days=1, hours=1)).isoformat()
    c.execute(
        "UPDATE wishes SET status='claimed', claimer='dave', claimed_at=?, expires_at=? WHERE id=?",
        (second_claim_ts, second_exp, expired),
    )
    c.commit()
    later = NOW + timedelta(days=2)
    result = expiry_sweep.commit(c, later)
    dave = [x for x in result["released"] if x["wish_id"] == expired][0]
    assert dave["claimer"] == "dave"

    rows = release_ledger.for_wish(c, expired)
    # same wish, two distinct locks -> two ledger rows keyed by claimed_at
    assert len(rows) == 2
    assert {r["claimer"] for r in rows} == {"ghost", "dave"}
    assert len({r["claimed_at"] for r in rows}) == 2
