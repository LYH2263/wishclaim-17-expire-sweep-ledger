"""Projection-only endpoints."""
from fastapi import APIRouter, HTTPException

from app.db import connect
from app.modules.projections import detail

router = APIRouter(tags=["projections"])


@router.get("/api/wishes/{wid}/events")
def wish_events(wid: int):
    c = connect()
    wish = detail.get_wish(c, wid)
    if not wish:
        c.close()
        raise HTTPException(404, "not found")
    events = detail.events_for_wish(c, wid)
    c.close()
    return {"events": events}
