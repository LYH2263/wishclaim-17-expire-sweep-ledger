"""Ledger persistence (I/O layer)."""
from app.modules.ledger.engine import make_lock_key

BATCH_COLS = (
    "batch_id", "source", "created_at",
    "candidate_count", "released_count", "skipped_count",
)


def insert_batch(c, batch: dict) -> None:
    c.execute(
        "INSERT INTO sweep_batches(batch_id,source,created_at,candidate_count,"
        "released_count,skipped_count) VALUES (?,?,?,?,?,?)",
        tuple(batch[k] for k in BATCH_COLS),
    )


def insert_ledger_entries(c, batch_id: str, released_at: str, rows: list[dict]) -> int:
    """Insert one row per released lock. Returns rows actually booked."""
    inserted = 0
    for r in rows:
        cur = c.execute(
            "INSERT OR IGNORE INTO sweep_ledger"
            "(batch_id,wish_id,claimer,claimed_at,released_at,lock_key)"
            " VALUES (?,?,?,?,?,?)",
            (batch_id, r["wish_id"], r["claimer"], r["claimed_at"],
             released_at, make_lock_key(r["wish_id"], r["claimed_at"])),
        )
        inserted += cur.rowcount
    return inserted


def _entries_for(c, where: str, params=()) -> list[dict]:
    sql = (
        "SELECT l.wish_id AS wish_id, w.title AS title, l.claimer AS claimer,"
        " l.claimed_at AS claimed_at, l.released_at AS released_at"
        " FROM sweep_ledger l LEFT JOIN wishes w ON w.id = l.wish_id "
        + where
        + " ORDER BY l.id ASC"
    )
    return [dict(r) for r in c.execute(sql, params)]


def _batch_from_row(c, row) -> dict:
    batch = {k: row[k] for k in BATCH_COLS}
    batch["entries"] = _entries_for(
        c, "WHERE l.batch_id=?", (batch["batch_id"],)
    )
    return batch


def get_batch(c, batch_id: str) -> dict | None:
    row = c.execute(
        "SELECT * FROM sweep_batches WHERE batch_id=?", (batch_id,)
    ).fetchone()
    return _batch_from_row(c, row) if row else None


def list_batches_with_entries(c, limit: int = 50) -> list[dict]:
    rows = c.execute(
        "SELECT * FROM sweep_batches ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_batch_from_row(c, r) for r in rows]


def entries_for_wish(c, wish_id: int) -> list[dict]:
    """Release events of one wish, newest first, with batch source."""
    rows = c.execute(
        "SELECT l.id AS id, l.batch_id AS batch_id, l.claimer AS claimer,"
        " l.released_at AS at, b.source AS source"
        " FROM sweep_ledger l JOIN sweep_batches b ON b.batch_id = l.batch_id"
        " WHERE l.wish_id=? ORDER BY l.id DESC",
        (wish_id,),
    ).fetchall()
    return [dict(r) for r in rows]
