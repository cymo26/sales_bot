"""
Database access layer for the SALES BOT dashboard.

All UI modules go through these helpers — no raw sessions in UI code.

Design rules:
- Every fetch is paginated at SQL level (LIMIT/OFFSET); nothing loads the whole table.
- All filtering happens in SQL WHERE clauses so pagination stays correct.
- Engine/sessionmaker are cached with @st.cache_resource (one pool per process).
- Fetches are cached with @st.cache_data and return plain dicts, never ORM objects.
- Writes are batched: one commit per user action, no per-row commits.
"""

import unicodedata
import uuid as uuid_lib
from contextlib import contextmanager
from datetime import datetime, timezone
from math import ceil

import streamlit as st
from sqlalchemy import create_engine, delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.orm import contains_eager, selectinload, sessionmaker

from app.core.database import DATABASE_URL_SYNC
from app.models.models import Company, Lead

# ── Constants ────────────────────────────────────────────────────────────────

LEADS_PAGE_SIZE = 50      # hard cap: never fetch/render more leads at once
COMPANIES_PAGE_SIZE = 20  # companies nest their leads, so the unit is smaller

# Canonical status values stored in the DB (model default is "new").
CANONICAL_STATUSES = ["new", "sent", "opened", "replied", "bounced"]

# Legacy Polish values previously written by the UI → canonical.
LEGACY_STATUS_MAP = {
    "nowy": "new",
    "wysłany": "sent",
    "otwarty": "opened",
    "odpowiedział": "replied",
    "odbitka": "bounced",
}


def _utcnow() -> datetime:
    """Naive UTC timestamp, matching the models' created_at/updated_at columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Engine / session management ──────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def get_engine():
    """One pooled engine per Streamlit process."""
    return create_engine(
        DATABASE_URL_SYNC,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,   # detect dropped connections before use
        pool_recycle=300,     # recycle before Neon's idle timeout kills them
        connect_args={"sslmode": "require"} if "neon" in DATABASE_URL_SYNC else {},
    )


@st.cache_resource(show_spinner=False)
def get_sessionmaker():
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)


@contextmanager
def db_session():
    """Short-lived session: rolls back on error, always closes."""
    session = get_sessionmaker()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@st.cache_resource(show_spinner=False)
def _unaccent_available() -> bool:
    """Enable Postgres unaccent for accent-insensitive search; fall back quietly."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
            conn.commit()
        return True
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def bootstrap() -> dict:
    """One-shot per process: migrate legacy Polish statuses to canonical values."""
    migrated = 0
    with db_session() as session:
        for legacy, canonical in LEGACY_STATUS_MAP.items():
            result = session.execute(
                update(Lead)
                .where(Lead.status == legacy)
                .values(status=canonical)
                .execution_options(synchronize_session=False)
            )
            migrated += result.rowcount or 0
        session.commit()
    return {"unaccent": _unaccent_available(), "migrated_statuses": migrated}


# ── Filter building blocks ───────────────────────────────────────────────────

def _fold_py(value: str) -> str:
    """Lowercase + strip diacritics so 'rys' matches 'ryś' (mirrors SQL unaccent)."""
    return (
        unicodedata.normalize("NFD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _fold_sql(column):
    """SQL-side counterpart of _fold_py; degrades to lower() without unaccent."""
    lowered = func.lower(column)
    return func.unaccent(lowered) if _unaccent_available() else lowered


def _lead_conditions(search="", locations=(), positions=(), statuses=(), tags=()):
    """WHERE clauses for lead queries. Callers must outerjoin Company for search."""
    conditions = []
    if search:
        term = f"%{_fold_py(search) if _unaccent_available() else search.lower()}%"
        full_name = func.concat_ws(" ", Lead.first_name, Lead.last_name)
        conditions.append(or_(
            _fold_sql(full_name).like(term),
            _fold_sql(Lead.email).like(term),
            _fold_sql(Company.name).like(term),
        ))
    if locations:
        conditions.append(Lead.location.in_(locations))
    if positions:
        conditions.append(Lead.position.in_(positions))
    if statuses:
        conditions.append(Lead.status.in_(statuses))
    if tags:
        conditions.append(
            func.string_to_array(Lead.tags, ",").op("&&")(array(list(tags)))
        )
    return conditions


def _lead_row(lead: Lead) -> dict:
    return {
        "id": str(lead.id),
        "first_name": lead.first_name or "",
        "last_name": lead.last_name or "",
        "full_name": f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "—",
        "email": lead.email,
        "position": lead.position or "—",
        "company": lead.company.name if lead.company else "—",
        "location": lead.location or "—",
        "linkedin_url": lead.linkedin_url or "",
        "tags": lead.tags or "",
        "status": lead.status,
        "notes": lead.notes or "",
        "created_at": lead.created_at.strftime("%Y-%m-%d"),
    }


# ── Leads: paginated fetch, metrics, filter options ──────────────────────────

@st.cache_data(show_spinner=False)
def fetch_leads_page(page=1, search="", locations=(), positions=(), statuses=(), tags=()):
    """One page of leads matching the filters. Returns {rows, total, pages, page}."""
    conditions = _lead_conditions(search, locations, positions, statuses, tags)
    with db_session() as session:
        total = session.execute(
            select(func.count(Lead.id))
            .select_from(Lead)
            .outerjoin(Company, Lead.company_id == Company.id)
            .where(*conditions)
        ).scalar_one()

        pages = max(1, ceil(total / LEADS_PAGE_SIZE))
        page = min(max(1, page), pages)

        leads = session.execute(
            select(Lead)
            .outerjoin(Company, Lead.company_id == Company.id)
            .options(contains_eager(Lead.company))
            .where(*conditions)
            .order_by(Lead.created_at.desc(), Lead.id)  # stable order across pages
            .limit(LEADS_PAGE_SIZE)
            .offset((page - 1) * LEADS_PAGE_SIZE)
        ).scalars().all()

        return {"rows": [_lead_row(l) for l in leads], "total": total,
                "pages": pages, "page": page}


@st.cache_data(show_spinner=False)
def fetch_lead_metrics(search="", locations=(), positions=(), statuses=(), tags=()):
    """Summary metrics for the filtered set — one aggregate query, no row loading."""
    conditions = _lead_conditions(search, locations, positions, statuses, tags)
    with db_session() as session:
        total, new, companies, with_position = session.execute(
            select(
                func.count(Lead.id),
                func.count(Lead.id).filter(Lead.status == "new"),
                func.count(func.distinct(Lead.company_id)),
                func.count(Lead.id).filter(
                    Lead.position.isnot(None), Lead.position != ""
                ),
            )
            .select_from(Lead)
            .outerjoin(Company, Lead.company_id == Company.id)
            .where(*conditions)
        ).one()
    return {"total": total, "new": new, "companies": companies,
            "with_position": with_position}


@st.cache_data(show_spinner=False)
def fetch_lead_filter_options(search="", locations=(), positions=(), statuses=()):
    """Cascading DISTINCT options: each list ignores its own filter so already
    selected values stay visible and combinable."""
    def distinct_of(column, **active):
        conditions = _lead_conditions(search=search, **active)
        with db_session() as session:
            values = session.execute(
                select(func.distinct(column))
                .select_from(Lead)
                .outerjoin(Company, Lead.company_id == Company.id)
                .where(column.isnot(None), column != "", *conditions)
                .order_by(column)
            ).scalars().all()
        return list(values)

    return {
        "locations": distinct_of(Lead.location, positions=positions, statuses=statuses),
        "positions": distinct_of(Lead.position, locations=locations, statuses=statuses),
        "statuses": distinct_of(Lead.status, locations=locations, positions=positions),
    }


@st.cache_data(show_spinner=False)
def fetch_lead_detail(lead_id: str):
    """Full detail for the profile dialog. Returns a dict or None."""
    with db_session() as session:
        lead = session.execute(
            select(Lead)
            .options(selectinload(Lead.company))
            .where(Lead.id == uuid_lib.UUID(lead_id))
        ).scalar_one_or_none()
        if lead is None:
            return None
        row = _lead_row(lead)
        row["industry"] = lead.company.industry if lead.company else None
        row["size_range"] = lead.company.size_range if lead.company else None
        return row


def fetch_leads_for_export(search="", locations=(), positions=(), statuses=(), tags=()):
    """The FULL filtered set, columns matching the outreach CSV. This is the one
    sanctioned exception to pagination: it never renders, runs only on an
    explicit export click, and selects plain tuples (no ORM objects)."""
    conditions = _lead_conditions(search, locations, positions, statuses, tags)
    with db_session() as session:
        rows = session.execute(
            select(Lead.email, Lead.first_name, Lead.last_name, Company.name,
                   Lead.position, Lead.location, Lead.status)
            .outerjoin(Company, Lead.company_id == Company.id)
            .where(*conditions)
            .order_by(Lead.created_at.desc(), Lead.id)
        ).all()
    return [
        {
            "Email": email,
            "First Name": first or "",
            "Last Name": last or "",
            "Company": company or "—",
            "Position": position or "—",
            "Location": location or "—",
            "Status": status,
        }
        for email, first, last, company, position, location, status in rows
    ]


# ── Companies: paginated fetch ───────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def fetch_companies_page(page=1, search="", locations=(), tags=()):
    """One page of companies with nested leads. Tag filter narrows both which
    companies appear (EXISTS) and which nested leads are shown."""
    conditions = []
    if search:
        term = f"%{_fold_py(search) if _unaccent_available() else search.lower()}%"
        conditions.append(_fold_sql(Company.name).like(term))
    if locations:
        conditions.append(Company.location.in_(locations))
    if tags:
        tag_match = func.string_to_array(Lead.tags, ",").op("&&")(array(list(tags)))
        conditions.append(
            select(Lead.id)
            .where(Lead.company_id == Company.id, tag_match)
            .exists()
        )

    wanted_tags = {t.upper() for t in tags}

    def lead_matches(lead: Lead) -> bool:
        if not wanted_tags:
            return True
        lead_tags = {t.strip().upper() for t in (lead.tags or "").split(",") if t.strip()}
        return bool(lead_tags & wanted_tags)

    with db_session() as session:
        total = session.execute(
            select(func.count(Company.id)).where(*conditions)
        ).scalar_one()

        pages = max(1, ceil(total / COMPANIES_PAGE_SIZE))
        page = min(max(1, page), pages)

        companies = session.execute(
            select(Company)
            .options(selectinload(Company.leads))
            .where(*conditions)
            .order_by(Company.name, Company.id)
            .limit(COMPANIES_PAGE_SIZE)
            .offset((page - 1) * COMPANIES_PAGE_SIZE)
        ).scalars().all()

        rows = [
            {
                "name": co.name,
                "domain": co.domain,
                "industry": co.industry or "—",
                "location": co.location or "—",
                "size_range": co.size_range or "—",
                "leads": [_lead_row(l) for l in co.leads if lead_matches(l)],
            }
            for co in companies
        ]
        return {"rows": rows, "total": total, "pages": pages, "page": page}


@st.cache_data(show_spinner=False)
def fetch_company_locations():
    """Distinct company locations (was wrongly built from lead locations)."""
    with db_session() as session:
        return list(session.execute(
            select(func.distinct(Company.location))
            .where(Company.location.isnot(None), Company.location != "")
            .order_by(Company.location)
        ).scalars().all())


# ── Writes: lead CRUD ────────────────────────────────────────────────────────

def _domain_slug(company_name: str) -> str:
    """Same slug rule the app has always used, so existing rows keep matching."""
    return company_name.lower().replace(" ", "-")[:50]


def _get_or_create_companies(session, names):
    """Batch get-or-create keyed by domain (the real unique key, not name).
    Returns {original name: Company}. Flushes once for new rows."""
    by_domain = {}
    for name in names:
        by_domain.setdefault(_domain_slug(name), name)

    existing = session.execute(
        select(Company).where(Company.domain.in_(by_domain.keys()))
    ).scalars().all()
    companies = {co.domain: co for co in existing}

    new_companies = [
        Company(name=name, domain=domain)
        for domain, name in by_domain.items()
        if domain not in companies
    ]
    if new_companies:
        session.add_all(new_companies)
        session.flush()
        companies.update({co.domain: co for co in new_companies})

    return {name: companies[_domain_slug(name)] for name in names}


def create_leads(leads: list) -> dict:
    """Insert leads from the Quick Add dialog in one transaction.
    Each dict carries lead fields plus 'company_name'.
    Returns {'added': int, 'skipped': [emails already in DB or repeated]}."""
    emails = [ld["email"] for ld in leads]
    with db_session() as session:
        existing = set(session.execute(
            select(Lead.email).where(Lead.email.in_(emails))
        ).scalars().all())

        skipped, to_add, seen = [], [], set()
        for ld in leads:
            if ld["email"] in existing or ld["email"] in seen:
                skipped.append(ld["email"])
                continue
            seen.add(ld["email"])
            to_add.append(dict(ld))

        companies = _get_or_create_companies(
            session, {ld["company_name"] for ld in to_add}
        )
        for ld in to_add:
            company = companies[ld.pop("company_name")]
            session.add(Lead(company_id=company.id, **ld))
        session.commit()

    invalidate_caches()
    return {"added": len(to_add), "skipped": skipped}


def update_lead(lead_id: str, status: str, notes) -> bool:
    """Save the profile dialog. Returns True if anything actually changed."""
    notes = notes.strip() or None if notes else None
    with db_session() as session:
        lead = session.get(Lead, uuid_lib.UUID(lead_id))
        if lead is None:
            return False
        if lead.status == status and lead.notes == notes:
            return False
        lead.status = status
        lead.notes = notes
        lead.updated_at = _utcnow()
        session.commit()

    invalidate_caches()
    return True


def delete_leads(lead_ids: list) -> int:
    """Bulk delete by id — single DELETE statement, single commit."""
    if not lead_ids:
        return 0
    with db_session() as session:
        result = session.execute(
            delete(Lead)
            .where(Lead.id.in_([uuid_lib.UUID(i) for i in lead_ids]))
            .execution_options(synchronize_session=False)
        )
        session.commit()

    invalidate_caches()
    return result.rowcount or 0


# ── Writes: bulk actions on the whole filtered set ───────────────────────────

def _filtered_lead_ids_query(search, locations, positions, statuses, tags):
    return (
        select(Lead.id)
        .outerjoin(Company, Lead.company_id == Company.id)
        .where(*_lead_conditions(search, locations, positions, statuses, tags))
    )


def bulk_set_status(new_status: str, search="", locations=(), positions=(),
                    statuses=(), tags=()) -> int:
    """Single UPDATE ... WHERE id IN (filtered set). No row loading at all."""
    ids_query = _filtered_lead_ids_query(search, locations, positions, statuses, tags)
    with db_session() as session:
        result = session.execute(
            update(Lead)
            .where(Lead.id.in_(ids_query))
            .values(status=new_status, updated_at=_utcnow())
            .execution_options(synchronize_session=False)
        )
        session.commit()

    invalidate_caches()
    return result.rowcount or 0


def bulk_add_tags(new_tags: list, search="", locations=(), positions=(),
                  statuses=(), tags=()) -> int:
    """Merge tags into every filtered lead: one SELECT, one executemany UPDATE
    keyed by primary key, one commit."""
    ids_query = _filtered_lead_ids_query(search, locations, positions, statuses, tags)
    now = _utcnow()
    with db_session() as session:
        rows = session.execute(
            select(Lead.id, Lead.tags).where(Lead.id.in_(ids_query))
        ).all()

        payload = []
        for lead_id, current in rows:
            existing = {t.strip() for t in (current or "").split(",") if t.strip()}
            merged = ",".join(sorted(existing | set(new_tags)))
            if merged != (current or ""):
                payload.append({"id": lead_id, "tags": merged, "updated_at": now})

        if payload:
            session.execute(update(Lead), payload)
            session.commit()

    invalidate_caches()
    return len(payload)


# ── Writes: CSV import ───────────────────────────────────────────────────────

def import_leads(records: list, tags: list) -> dict:
    """Batched CSV import. `records` are pre-mapped dicts with lead fields plus
    optional 'company_name'. One duplicate pre-check, one company batch, one
    add_all, ONE commit — no per-row round trips.
    Returns {'added', 'skipped_duplicates', 'skipped_invalid'}."""
    valid = [r for r in records if r.get("email")]
    skipped_invalid = len(records) - len(valid)

    if not valid:
        return {"added": 0, "skipped_duplicates": 0, "skipped_invalid": skipped_invalid}

    tag_value = ",".join(sorted(set(tags))) if tags else None

    with db_session() as session:
        existing = set(session.execute(
            select(Lead.email).where(Lead.email.in_([r["email"] for r in valid]))
        ).scalars().all())

        to_add, seen = [], set()
        for record in valid:
            if record["email"] in existing or record["email"] in seen:
                continue
            seen.add(record["email"])
            to_add.append(dict(record))

        companies = _get_or_create_companies(
            session, {r["company_name"] for r in to_add if r.get("company_name")}
        )
        for record in to_add:
            company_name = record.pop("company_name", None)
            if company_name:
                record["company_id"] = companies[company_name].id
            if tag_value:
                record["tags"] = tag_value

        session.add_all(Lead(**record) for record in to_add)
        session.commit()

    invalidate_caches()
    return {
        "added": len(to_add),
        "skipped_duplicates": len(valid) - len(to_add),
        "skipped_invalid": skipped_invalid,
    }


# ── Cache control ────────────────────────────────────────────────────────────

def invalidate_caches():
    """Clear every cached fetch after any write."""
    fetch_leads_page.clear()
    fetch_lead_metrics.clear()
    fetch_lead_filter_options.clear()
    fetch_lead_detail.clear()
    fetch_companies_page.clear()
    fetch_company_locations.clear()
