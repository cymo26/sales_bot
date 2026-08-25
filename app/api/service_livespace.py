"""Orchestrates Livespace sync: TTL check -> livespace_client calls -> write
the livespace_* columns back onto a Lead. Mirrors service.py's convention
(session: Session first, session.get -> guard -> mutate -> commit) except
async, since it awaits the httpx client.

Fail-soft throughout (see the architecture plan's section H): a Livespace
problem never raises out of here. Errors leave the previously-cached
owner/deal untouched and set sync_status="error" without touching
last_synced_at, so the background sweep keeps retrying; a legitimate
not_found is a normal, successful sync.
"""

from __future__ import annotations

import asyncio
import logging
import uuid as uuid_lib
from datetime import timedelta

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api import livespace_client as lc
from app.api.service import _engaged_label, _utcnow
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import Lead

logger = logging.getLogger(__name__)


def _company_engagement(session: Session, lead: Lead) -> tuple[bool, str | None]:
    if not lead.company_id:
        return False, None
    row = session.execute(
        select(Lead.livespace_owner_name, Lead.livespace_deal_name)
        .where(
            Lead.company_id == lead.company_id,
            Lead.id != lead.id,
            or_(Lead.livespace_owner_name.isnot(None), Lead.livespace_deal_name.isnot(None)),
        )
        .limit(1)
    ).first()
    if not row:
        return False, None
    return True, _engaged_label(*row)


def _result(lead: Lead, session: Session) -> dict:
    engaged, engaged_via = _company_engagement(session, lead)
    return {
        "livespace_sync_status": lead.livespace_sync_status,
        "livespace_owner_name": lead.livespace_owner_name,
        "livespace_deal_name": lead.livespace_deal_name,
        "livespace_last_synced_at": lead.livespace_last_synced_at,
        "company_livespace_engaged": engaged,
        "company_livespace_engaged_via": engaged_via,
    }


async def sync_lead_livespace_status(
    session: Session,
    client: httpx.AsyncClient,
    lead_id: str,
    force: bool = False,
    livespace_session: lc.LivespaceSession | None = None,
) -> dict:
    try:
        lead = session.get(Lead, uuid_lib.UUID(lead_id))
    except ValueError:
        lead = None
    if lead is None:
        return {"livespace_sync_status": None}

    if not settings.livespace_enabled:
        lead.livespace_sync_status = "disabled"
        session.commit()
        return _result(lead, session)

    if not lead.email:
        # Can't match without an email — leave untouched rather than
        # inventing a fifth sync_status value; the sweep's own selection
        # query already excludes emailless leads so this doesn't loop.
        return _result(lead, session)

    if not force and lead.livespace_last_synced_at is not None:
        age = _utcnow() - lead.livespace_last_synced_at
        if age < timedelta(minutes=settings.livespace_cache_ttl_minutes):
            return _result(lead, session)

    try:
        ls_session = livespace_session or await lc.get_session(client, settings)
        contact = await lc.find_contact_by_email(client, settings, ls_session, lead.email)
        if contact is None:
            lead.livespace_sync_status = "not_found"
            lead.livespace_last_synced_at = _utcnow()
            session.commit()
            return _result(lead, session)

        deal = await lc.find_active_deal(client, settings, ls_session, contact.contact_id, contact.company_id)
        lead.livespace_id = contact.contact_id
        lead.livespace_owner_name = contact.owner_name
        lead.livespace_deal_name = deal.name if deal else None
        lead.livespace_sync_status = "matched"
        lead.livespace_last_synced_at = _utcnow()
        session.commit()
    except lc.LivespaceError as e:
        logger.warning("Livespace sync failed for lead %s: %s", lead_id, e)
        lead.livespace_sync_status = "error"
        session.commit()

    return _result(lead, session)


async def sync_stale_leads_batch(session: Session, client: httpx.AsyncClient, limit: int = 200) -> dict:
    if not settings.livespace_enabled:
        return {"checked": 0, "matched": 0, "errors": 0, "skipped": "disabled"}

    cutoff = _utcnow() - timedelta(minutes=settings.livespace_cache_ttl_minutes)
    stale_ids = session.execute(
        select(Lead.id)
        .where(
            Lead.email.isnot(None),
            Lead.email != "",
            or_(Lead.livespace_last_synced_at.is_(None), Lead.livespace_last_synced_at < cutoff),
        )
        .order_by(Lead.livespace_last_synced_at.asc().nulls_first())
        .limit(limit)
    ).scalars().all()

    if not stale_ids:
        return {"checked": 0, "matched": 0, "errors": 0}

    # One session for the whole batch (per the architecture plan: fetching a
    # fresh token per-lead would multiply auth calls for no benefit).
    ls_session = await lc.get_session(client, settings)
    semaphore = asyncio.Semaphore(settings.livespace_max_concurrency)

    async def run_one(lead_id: uuid_lib.UUID) -> dict:
        # A SQLAlchemy Session isn't safe for concurrent use — even under
        # asyncio's single-threaded cooperative model, two tasks interleaved
        # on the same Session can corrupt its transaction/identity-map state.
        # Each concurrent task gets its own short-lived session instead of
        # sharing the outer `session` (which is only used for the SELECT
        # above, which already completed before any of these start).
        task_session = SessionLocal()
        try:
            async with semaphore:
                return await sync_lead_livespace_status(
                    task_session, client, str(lead_id), force=True, livespace_session=ls_session
                )
        finally:
            task_session.close()

    results = await asyncio.gather(*(run_one(lid) for lid in stale_ids))
    matched = sum(1 for r in results if r.get("livespace_sync_status") == "matched")
    errors = sum(1 for r in results if r.get("livespace_sync_status") == "error")
    return {"checked": len(results), "matched": matched, "errors": errors}
