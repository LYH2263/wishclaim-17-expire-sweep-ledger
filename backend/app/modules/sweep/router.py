"""Expiry sweep endpoints: dry-run preview and commit."""
from datetime import datetime, timezone

from fastapi import APIRouter

from app.db import connect
from app.modules.sweep import service

router = APIRouter(prefix="/api/sweep", tags=["sweep"])


@router.post("/dry-run")
def dry_run():
    c = connect()
    try:
        return service.dry_run(c, datetime.now(timezone.utc))
    finally:
        c.close()


@router.post("/commit")
def commit():
    c = connect()
    try:
        return service.commit_sweep(c, datetime.now(timezone.utc))
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
