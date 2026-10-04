"""Sweep service: dry-run preview and two-phase commit (I/O layer)."""
from datetime import datetime
from uuid import uuid4

from app.modules.ledger import repo as ledger_repo
from app.modules.ledger.engine import new_batch_id
from app.modules.sweep.engine import candidate_from_row

# Coarse filter only; expiry itself is decided in Python via claim_lock so
# ISO timestamps are never compared as SQL strings.
_CANDIDATE_SQL = (
    "SELECT id,status,claimer,claimed_at,expires_at FROM wishes"
    " WHERE status='claimed' AND expires_at IS NOT NULL AND claimed_at IS NOT NULL"
    " ORDER BY id"
)


def select_candidates(c, now: datetime, wish_id: int | None = None) -> list[dict]:
    """Single source of truth shared by dry-run and commit."""
    sql = _CANDIDATE_SQL + (" AND id=?" if wish_id is not None else "")
    params = (wish_id,) if wish_id is not None else ()
    out = []
    for r in c.execute(sql, params):
        cand = candidate_from_row(r, now)
        if cand:
            out.append(cand)
    return out


def dry_run(c, now: datetime) -> dict:
    """Read-only: list what a commit would release. Never writes."""
    candidates = select_candidates(c, now)
    return {
        "checked_at": now.isoformat(),
        "count": len(candidates),
        "candidates": candidates,
    }


def apply_candidate(c, cand: dict) -> bool:
    """Release one pinned lock incarnation. False if it changed since snap."""
    cur = c.execute(
        "UPDATE wishes SET status='open', claimer=NULL,"
        " claimed_at=NULL, expires_at=NULL"
        " WHERE id=? AND status='claimed' AND claimed_at=? AND expires_at=?",
        (cand["wish_id"], cand["claimed_at"], cand["expires_at"]),
    )
    return cur.rowcount == 1


def commit_sweep(c, now: datetime, source: str = "sweep",
                 wish_id: int | None = None, commit: bool = True) -> dict:
    """Release expired locks and append ledger rows in one transaction.

    Pass wish_id to restrict to one row (claim-endpoint reclaim path, which
    also passes commit=False to join the new-lock UPDATE in the same txn).
    Rows that changed since the candidate snapshot are skipped, not booked.
    """
    candidates = select_candidates(c, now, wish_id)
    released: list[dict] = []
    skipped: list[dict] = []
    for cand in candidates:
        if apply_candidate(c, cand):
            released.append({
                "wish_id": cand["wish_id"],
                "claimer": cand["claimer"],
                "claimed_at": cand["claimed_at"],
            })
        else:
            # Manually released / fulfilled / reclaimed / already swept.
            skipped.append({"wish_id": cand["wish_id"], "reason": "changed"})

    released_at = now.isoformat()
    batch_id = None
    if released:
        batch_id = new_batch_id(now, uuid4().hex)
        ledger_repo.insert_batch(c, {
            "batch_id": batch_id,
            "source": source,
            "created_at": released_at,
            "candidate_count": len(candidates),
            "released_count": len(released),
            "skipped_count": len(skipped),
        })
        ledger_repo.insert_ledger_entries(c, batch_id, released_at, released)

    if commit:
        c.commit()
    return {
        "batch_id": batch_id,
        "source": source,
        "released_at": released_at,
        "candidate_count": len(candidates),
        "released_count": len(released),
        "skipped_count": len(skipped),
        "released": [{"wish_id": r["wish_id"], "claimer": r["claimer"]} for r in released],
        "skipped": skipped,
    }
