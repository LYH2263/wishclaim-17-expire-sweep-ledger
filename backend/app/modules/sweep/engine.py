"""Pure sweep decisions: candidate selection reuses claim_lock semantics."""
from datetime import datetime

from app.engines.claim_lock import release_if_expired


def is_expired_lock(status: str, expires_at: str | None, now: datetime) -> bool:
    return release_if_expired(status, expires_at, now) is not None


def candidate_from_row(row, now: datetime) -> dict | None:
    """Return a release candidate for a claimed-and-expired row, else None.

    claimed_at identifies this incarnation of the lock; it survives the
    release in the ledger even though the wishes row clears it.
    """
    if not is_expired_lock(row["status"], row["expires_at"], now):
        return None
    return {
        "wish_id": row["id"],
        "claimer": row["claimer"],
        "claimed_at": row["claimed_at"],
        "expires_at": row["expires_at"],
    }
