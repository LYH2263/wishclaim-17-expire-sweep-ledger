"""Read-only ledger API."""
from fastapi import APIRouter, HTTPException

from app.db import connect
from app.modules.ledger import repo

router = APIRouter(prefix="/api/ledger", tags=["ledger"])


@router.get("")
def list_ledger(limit: int = 50):
    c = connect()
    batches = repo.list_batches_with_entries(c, limit)
    c.close()
    return {"batches": batches}


@router.get("/{batch_id}")
def get_batch(batch_id: str):
    c = connect()
    batch = repo.get_batch(c, batch_id)
    c.close()
    if not batch:
        raise HTTPException(404, "batch not found")
    return batch
