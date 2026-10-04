"""Detail projection: one wish plus its release-event timeline."""
from app.modules.ledger import repo as ledger_repo

_WISH_SQL = (
    "SELECT id,title,note,status,claimer,claimed_at,expires_at,data_quality"
    " FROM wishes WHERE id=?"
)


def get_wish(c, wish_id: int) -> dict | None:
    r = c.execute(_WISH_SQL, (wish_id,)).fetchone()
    return dict(r) if r else None


def events_for_wish(c, wish_id: int) -> list[dict]:
    events = []
    for e in ledger_repo.entries_for_wish(c, wish_id):
        events.append({
            "id": e["id"],
            "type": "sweep_release",
            "at": e["at"],
            "batch_id": e["batch_id"],
            "claimer": e["claimer"],
            "source": e["source"],
        })
    return events
