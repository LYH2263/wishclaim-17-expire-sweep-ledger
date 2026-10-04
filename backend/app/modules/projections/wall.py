"""Wall projection: read-only wish rows with a derived sweep_eligible flag."""
from app.modules.sweep.engine import is_expired_lock

_WISH_COLS = (
    "id", "title", "note", "status", "claimer",
    "claimed_at", "expires_at", "data_quality",
)


def _decorate(rows, now) -> list[dict]:
    out = []
    for r in rows:
        d = dict(r)
        d["sweep_eligible"] = is_expired_lock(d["status"], d["expires_at"], now)
        out.append(d)
    return out


def list_wishes(c, now) -> list[dict]:
    rows = c.execute(
        "SELECT id,title,note,status,claimer,claimed_at,expires_at,data_quality"
        " FROM wishes ORDER BY id DESC"
    ).fetchall()
    return _decorate(rows, now)


def list_for_claimer(c, now, claimer: str) -> list[dict]:
    rows = c.execute(
        "SELECT id,title,note,status,claimer,claimed_at,expires_at,data_quality"
        " FROM wishes WHERE claimer=? ORDER BY id DESC",
        (claimer,),
    ).fetchall()
    return _decorate(rows, now)
