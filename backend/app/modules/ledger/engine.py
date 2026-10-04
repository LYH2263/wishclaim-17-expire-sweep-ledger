"""Pure helpers for sweep ledger identities (no I/O)."""
from datetime import datetime


def make_lock_key(wish_id: int, claimed_at: str) -> str:
    """Identity of one lock incarnation.

    A wish can be claimed, swept, claimed again... each incarnation gets a
    distinct claimed_at, hence a distinct key; re-committing the same
    incarnation collides and must not be booked twice.
    """
    return f"{wish_id}:{claimed_at}"


def new_batch_id(now: datetime, token: str) -> str:
    return "B" + now.strftime("%Y%m%dT%H%M%S%f") + "-" + token[:8]
