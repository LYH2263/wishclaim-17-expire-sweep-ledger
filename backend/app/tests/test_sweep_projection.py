from datetime import timedelta
from app.tests.test_expiry_sweep import db, add, setup_mixed, NOW
from app.modules import expiry_sweep, sweep_projection


def test_wall_detail_ledger_share_same_batch():
    c = db()
    expired, _, _, _ = setup_mixed(c)
    result = expiry_sweep.commit(c, NOW)
    batch = result["batch_id"]

    wall = {w["id"]: w for w in sweep_projection.wall_rows(c, NOW)}
    assert wall[expired]["status"] == "open"
    assert wall[expired]["claimable"] is True
    assert wall[expired]["released_batch_id"] == batch

    events = sweep_projection.wish_events(c, expired)
    assert len(events) == 1
    assert events[0]["batch_id"] == batch
    assert events[0]["claimer"] == "ghost"
    assert events[0]["type"] == "ttl_released"

    ledger = sweep_projection.ledger_view(c)
    assert len(ledger) == 1
    assert ledger[0]["batch_id"] == batch
    assert [e["wish_id"] for e in ledger[0]["entries"]] == [expired]
