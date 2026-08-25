"""Livespace ownership-check endpoint — Lead Profile modal's "Odśwież status
Livespace" action. The read path (cached livespace_* fields) is folded into
the existing GET /api/leads/{id} response instead of a second endpoint here,
to avoid an extra round trip on every lead open."""

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import service_livespace
from app.api.deps import get_db, get_livespace_client
from app.api.schemas import LivespaceRefreshOut

router = APIRouter(prefix="/api/leads", tags=["livespace"])


@router.post("/{lead_id}/livespace-refresh", response_model=LivespaceRefreshOut)
async def refresh_livespace(
    lead_id: str,
    db: Session = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_livespace_client),
):
    return await service_livespace.sync_lead_livespace_status(db, client, lead_id, force=True)
