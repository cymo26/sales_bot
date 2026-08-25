"""Database service layer for the FastAPI app.

Streamlit-free port of db/queries.py: identical SQL, identical algorithms
(dedupe, domain normalization, location aggregation, industry-conflict dry
run, batched writes). The only differences are mechanical:
  - each function takes an already-open `session: Session` (FastAPI injects
    one per request via app.api.deps.get_db) instead of opening its own;
  - @st.cache_data / @st.cache_resource are dropped — a stateless HTTP
    endpoint doesn't have the same rerun-caching problem Streamlit had, and
    dropping them is a performance change only, not a behavior change;
  - `_unaccent_available()` is cached in a plain module-level flag instead
    of st.cache_resource.
"""

import re
import unicodedata
import uuid as uuid_lib
from datetime import datetime, timezone
from math import ceil

from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.orm import Session, contains_eager, selectinload

from app.api.constants import DEFAULT_INDUSTRIES, LEADS_PAGE_SIZE, COMPANIES_PAGE_SIZE, LEGACY_STATUS_MAP
from app.models.models import Company, Lead


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Bootstrap (run once at app startup — see main.py) ───────────────────────

_unaccent_flag: bool | None = None


def _unaccent_available(session: Session) -> bool:
    global _unaccent_flag
    if _unaccent_flag is None:
        try:
            session.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
            session.commit()
            _unaccent_flag = True
        except Exception:
            session.rollback()
            _unaccent_flag = False
    return _unaccent_flag


def bootstrap(session: Session) -> dict:
    """Idempotent schema fixes + legacy status migration. Safe to call more
    than once (e.g. also by the Streamlit app) — every statement is a no-op
    when already applied."""
    migrated = 0
    session.execute(text("ALTER TABLE companies ALTER COLUMN domain DROP NOT NULL"))
    session.execute(text("ALTER TABLE leads ALTER COLUMN email DROP NOT NULL"))
    session.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS livespace_owner_name VARCHAR"))
    session.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS livespace_deal_name VARCHAR"))
    session.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS livespace_sync_status VARCHAR"))
    session.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS livespace_last_synced_at TIMESTAMP"))
    session.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS livespace_company_id VARCHAR"))
    for legacy, canonical in LEGACY_STATUS_MAP.items():
        result = session.execute(
            update(Lead)
            .where(Lead.status == legacy)
            .values(status=canonical)
            .execution_options(synchronize_session=False)
        )
        migrated += result.rowcount or 0
    session.commit()
    return {"unaccent": _unaccent_available(session), "migrated_statuses": migrated}


# ── Filter building blocks ───────────────────────────────────────────────────

def _fold_py(value: str) -> str:
    return (
        unicodedata.normalize("NFD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _fold_sql(column, session: Session):
    lowered = func.lower(column)
    return func.unaccent(lowered) if _unaccent_available(session) else lowered


def _lead_conditions(session: Session, search="", locations=(), positions=(), statuses=(),
                     tags=(), companies=(), email_only=False, no_email=False):
    conditions = []
    if search:
        term = f"%{_fold_py(search) if _unaccent_available(session) else search.lower()}%"
        full_name = func.concat_ws(" ", Lead.first_name, Lead.last_name)
        conditions.append(or_(
            _fold_sql(full_name, session).like(term),
            _fold_sql(Lead.email, session).like(term),
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
    if companies:
        conditions.append(Company.name.in_(companies))
    if email_only:
        conditions.append(Lead.email.isnot(None))
        conditions.append(Lead.email != "")
    if no_email:
        conditions.append(or_(Lead.email.is_(None), Lead.email == ""))
    return conditions


def _lead_to_dict(lead: Lead) -> dict:
    """Personal livespace_* fields only. company_livespace_engaged/_via are
    stamped on separately by each caller — the three call sites (a paginated
    list, a single detail fetch, and a company's already-loaded leads) each
    compute "is a *different* lead at this company engaged" a different, more
    efficient way, so there's no single shared computation to put here."""
    return {
        "id": str(lead.id),
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "email": lead.email,
        "position": lead.position,
        "company_id": str(lead.company_id) if lead.company_id else None,
        "company_name": lead.company.name if lead.company else None,
        "location": lead.location,
        "linkedin_url": lead.linkedin_url,
        "tags": [t.strip() for t in (lead.tags or "").split(",") if t.strip()],
        "status": lead.status,
        "notes": lead.notes,
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
        "livespace_owner_name": lead.livespace_owner_name,
        "livespace_deal_name": lead.livespace_deal_name,
        "livespace_sync_status": lead.livespace_sync_status,
        "livespace_last_synced_at": lead.livespace_last_synced_at,
        "company_livespace_engaged": False,
        "company_livespace_engaged_via": None,
    }


def _engaged_label(owner_name, deal_name) -> str | None:
    parts = [p for p in (owner_name, deal_name) if p]
    return " – ".join(parts) if parts else None


def _stamp_company_engagement(rows: list[dict], leads: list[Lead], session: Session) -> None:
    """Mutates `rows` (parallel to `leads`) in place, setting
    company_livespace_engaged/_via from OTHER leads at the same company —
    one batched query for the whole page, not one per row."""
    company_ids = {l.company_id for l in leads if l.company_id}
    if not company_ids:
        return
    engaged_rows: dict[str, list[tuple[str, str]]] = {}
    for lid, cid, owner, deal in session.execute(
        select(Lead.id, Lead.company_id, Lead.livespace_owner_name, Lead.livespace_deal_name)
        .where(
            Lead.company_id.in_(company_ids),
            or_(Lead.livespace_owner_name.isnot(None), Lead.livespace_deal_name.isnot(None)),
        )
    ).all():
        label = _engaged_label(owner, deal)
        if label:
            engaged_rows.setdefault(str(cid), []).append((str(lid), label))

    for row, lead in zip(rows, leads):
        if not lead.company_id:
            continue
        for other_lead_id, label in engaged_rows.get(str(lead.company_id), []):
            if other_lead_id != str(lead.id):
                row["company_livespace_engaged"] = True
                row["company_livespace_engaged_via"] = label
                break


# ── Leads: paginated fetch, metrics, filter options ──────────────────────────

def fetch_leads_page(session: Session, page=1, search="", locations=(), positions=(),
                     statuses=(), tags=(), companies=(), email_only=False, no_email=False):
    conditions = _lead_conditions(session, search, locations, positions, statuses, tags,
                                  companies=companies, email_only=email_only, no_email=no_email)
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
        .order_by(Lead.created_at.desc(), Lead.id)
        .limit(LEADS_PAGE_SIZE)
        .offset((page - 1) * LEADS_PAGE_SIZE)
    ).scalars().all()

    rows = [_lead_to_dict(l) for l in leads]
    _stamp_company_engagement(rows, leads, session)
    return {"rows": rows, "total": total, "pages": pages, "page": page}


def fetch_lead_metrics(session: Session, search="", locations=(), positions=(), statuses=(),
                       tags=(), companies=(), email_only=False, no_email=False):
    conditions = _lead_conditions(session, search, locations, positions, statuses, tags,
                                  companies=companies, email_only=email_only, no_email=no_email)
    total, new, n_companies, with_position = session.execute(
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
    return {"total": total, "new": new, "companies": n_companies,
            "with_position": with_position}


def fetch_lead_filter_options(session: Session, search="", locations=(), positions=(),
                              statuses=(), companies=(), email_only=False, no_email=False):
    def distinct_of(column, **active):
        conditions = _lead_conditions(session, search=search, email_only=email_only,
                                      no_email=no_email, **active)
        values = session.execute(
            select(func.distinct(column))
            .select_from(Lead)
            .outerjoin(Company, Lead.company_id == Company.id)
            .where(column.isnot(None), column != "", *conditions)
            .order_by(column)
        ).scalars().all()
        return list(values)

    return {
        "locations": distinct_of(Lead.location, positions=positions,
                                 statuses=statuses, companies=companies),
        "positions": distinct_of(Lead.position, locations=locations,
                                 statuses=statuses, companies=companies),
        "statuses": distinct_of(Lead.status, locations=locations,
                                positions=positions, companies=companies),
        "companies": distinct_of(Company.name, locations=locations,
                                 positions=positions, statuses=statuses),
    }


def fetch_lead_detail(session: Session, lead_id: str):
    try:
        uid = uuid_lib.UUID(lead_id)
    except ValueError:
        return None
    lead = session.execute(
        select(Lead)
        .options(selectinload(Lead.company))
        .where(Lead.id == uid)
    ).scalar_one_or_none()
    if lead is None:
        return None
    row = _lead_to_dict(lead)
    row["industry"] = lead.company.industry if lead.company else None
    row["size_range"] = lead.company.size_range if lead.company else None
    if lead.company_id:
        other = session.execute(
            select(Lead.livespace_owner_name, Lead.livespace_deal_name)
            .where(
                Lead.company_id == lead.company_id,
                Lead.id != lead.id,
                or_(Lead.livespace_owner_name.isnot(None), Lead.livespace_deal_name.isnot(None)),
            )
            .limit(1)
        ).first()
        if other:
            row["company_livespace_engaged"] = True
            row["company_livespace_engaged_via"] = _engaged_label(*other)
    return row


def fetch_leads_for_export(session: Session, search="", locations=(), positions=(),
                           statuses=(), tags=(), companies=(), email_only=False, no_email=False):
    """The FULL filtered set for the outreach CSV — Name + Email + Position only."""
    conditions = _lead_conditions(session, search, locations, positions, statuses, tags,
                                  companies=companies, email_only=email_only, no_email=no_email)
    rows = session.execute(
        select(Lead.first_name, Lead.last_name, Lead.email, Lead.position)
        .outerjoin(Company, Lead.company_id == Company.id)
        .where(*conditions)
        .order_by(Lead.created_at.desc(), Lead.id)
    ).all()
    return [
        {
            "Name": f"{first or ''} {last or ''}".strip(),
            "Email": email or "",
            "Position": position or "",
        }
        for first, last, email, position in rows
    ]


# ── Companies: paginated fetch ───────────────────────────────────────────────

def fetch_companies_page(session: Session, page=1, search="", locations=(), tags=()):
    conditions = []
    if search:
        term = f"%{_fold_py(search) if _unaccent_available(session) else search.lower()}%"
        conditions.append(_fold_sql(Company.name, session).like(term))
    if locations:
        cities = func.string_to_array(
            func.replace(Company.location, ", ", ","), ","
        )
        conditions.append(cities.op("&&")(array(list(locations))))
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

    def build_company_row(co: Company) -> dict:
        # co.leads is ALL of this company's leads (unfiltered by tags — the
        # tag filter only narrows which leads are *displayed*, engagement is
        # computed from the whole account regardless of the current filter).
        engaged_entries = [
            (str(l.id), _engaged_label(l.livespace_owner_name, l.livespace_deal_name))
            for l in co.leads
            if l.livespace_owner_name or l.livespace_deal_name
        ]
        lead_rows = []
        for l in co.leads:
            if not lead_matches(l):
                continue
            row = _lead_to_dict(l)
            for other_id, label in engaged_entries:
                if other_id != str(l.id):
                    row["company_livespace_engaged"] = True
                    row["company_livespace_engaged_via"] = label
                    break
            lead_rows.append(row)
        return {
            "id": str(co.id),
            "name": co.name,
            "domain": co.domain,
            "industry": co.industry,
            "location": co.location,
            "size_range": co.size_range,
            "livespace_engaged": bool(engaged_entries),
            "livespace_engaged_via": engaged_entries[0][1] if engaged_entries else None,
            "leads": lead_rows,
        }

    rows = [build_company_row(co) for co in companies]
    return {"rows": rows, "total": total, "pages": pages, "page": page}


def fetch_industries(session: Session):
    db_industries = session.execute(
        select(func.distinct(Company.industry))
        .where(Company.industry.isnot(None), Company.industry != "")
    ).scalars().all()

    merged, seen = [], set()
    for industry in DEFAULT_INDUSTRIES + list(db_industries):
        industry = industry.strip()
        if industry and industry.lower() not in seen:
            seen.add(industry.lower())
            merged.append(industry)
    return sorted(merged, key=str.lower)


def fetch_company_locations(session: Session):
    raw = session.execute(
        select(func.distinct(Company.location))
        .where(Company.location.isnot(None), Company.location != "")
    ).scalars().all()
    cities = {c.strip() for value in raw for c in value.split(",") if c.strip()}
    return sorted(cities, key=str.lower)


# ── Writes: lead CRUD ────────────────────────────────────────────────────────

def _domain_slug(company_name: str) -> str:
    return company_name.lower().replace(" ", "-")[:50]


def _normalize_domain(value) -> str | None:
    if not value:
        return None
    domain = str(value).strip().lower()
    domain = re.sub(r"^[a-z][a-z0-9+.-]*://", "", domain)
    domain = domain.split("/")[0].split("?")[0].split("#")[0]
    domain = domain.removeprefix("www.").strip(".")
    return domain or None


def _merge_locations(existing, new_locations) -> str | None:
    merged = [loc.strip() for loc in (existing or "").split(",") if loc.strip()]
    seen = {loc.casefold() for loc in merged}
    for loc in new_locations:
        loc = (loc or "").strip()
        if loc and loc.casefold() not in seen:
            seen.add(loc.casefold())
            merged.append(loc)
    return ", ".join(merged) or None


def _append_company_locations(pairs) -> None:
    companies, new_locations = {}, {}
    for company, location in pairs:
        if location and str(location).strip():
            companies[company.id] = company
            new_locations.setdefault(company.id, []).append(str(location))
    for company_id, values in new_locations.items():
        company = companies[company_id]
        company.location = _merge_locations(company.location, values)


def _get_or_create_companies(session: Session, name_domains: dict) -> dict:
    if not name_domains:
        return {}
    keys = {name: (domain or _domain_slug(name)) for name, domain in name_domains.items()}

    existing = session.execute(
        select(Company).where(or_(
            Company.domain.in_(set(keys.values())),
            Company.name.in_(set(name_domains)),
        ))
    ).scalars().all()
    by_domain = {co.domain: co for co in existing if co.domain}
    by_name = {co.name: co for co in existing}

    result, created = {}, {}
    for name, domain in name_domains.items():
        key = keys[name]
        company = by_domain.get(key) or by_name.get(name) or created.get(key)
        if company is None:
            company = Company(name=name, domain=key)
            created[key] = company
        elif domain and company.domain != domain and domain not in by_domain:
            company.domain = domain
            by_domain[domain] = company
        result[name] = company

    if created:
        session.add_all(created.values())
        session.flush()

    return result


def preview_industry_conflicts(session: Session, company_industries: dict) -> list:
    """DRY RUN — read-only, writes nothing."""
    wanted = {n: i.strip() for n, i in company_industries.items() if i and i.strip()}
    if not wanted:
        return []
    keys = {name: _domain_slug(name) for name in wanted}
    existing = session.execute(
        select(Company).where(or_(
            Company.domain.in_(set(keys.values())),
            Company.name.in_(set(wanted)),
        ))
    ).scalars().all()
    by_domain = {co.domain: co for co in existing if co.domain}
    by_name = {co.name: co for co in existing}

    conflicts = []
    for name, incoming in wanted.items():
        company = by_domain.get(keys[name]) or by_name.get(name)
        current = (company.industry or "").strip() if company else ""
        if current and current.lower() != incoming.lower():
            conflicts.append(
                {"company": name, "current": current, "incoming": incoming}
            )
    return conflicts


def create_leads(session: Session, leads: list) -> dict:
    """Insert leads from the Quick Add form in one transaction. Each dict
    carries lead fields plus 'company_name' and optionally 'company_industry'
    — callers resolve conflicts first via preview_industry_conflicts."""
    emails = [ld["email"] for ld in leads]
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
        session, {ld["company_name"]: None for ld in to_add}
    )

    for ld in to_add:
        industry = (ld.get("company_industry") or "").strip()
        if industry:
            company = companies[ld["company_name"]]
            if (company.industry or "").strip().lower() != industry.lower():
                company.industry = industry

    location_pairs = []
    for ld in to_add:
        ld.pop("company_industry", None)
        company = companies[ld.pop("company_name")]
        location_pairs.append((company, ld.get("location")))
        session.add(Lead(company_id=company.id, **ld))
    _append_company_locations(location_pairs)
    session.commit()

    return {"added": len(to_add), "skipped": skipped}


def update_lead(session: Session, lead_id: str, status: str, notes) -> bool:
    notes = notes.strip() or None if notes else None
    lead = session.get(Lead, uuid_lib.UUID(lead_id))
    if lead is None:
        return False
    if lead.status == status and lead.notes == notes:
        return False
    lead.status = status
    lead.notes = notes
    lead.updated_at = _utcnow()
    session.commit()
    return True


def delete_leads(session: Session, lead_ids: list) -> int:
    if not lead_ids:
        return 0
    result = session.execute(
        delete(Lead)
        .where(Lead.id.in_([uuid_lib.UUID(i) for i in lead_ids]))
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return result.rowcount or 0


# ── Writes: bulk actions on the whole filtered set ───────────────────────────

def _filtered_lead_ids_query(session: Session, search, locations, positions, statuses,
                             tags, companies=(), email_only=False, no_email=False):
    return (
        select(Lead.id)
        .outerjoin(Company, Lead.company_id == Company.id)
        .where(*_lead_conditions(session, search, locations, positions, statuses, tags,
                                  companies=companies, email_only=email_only, no_email=no_email))
    )


def bulk_set_status(session: Session, new_status: str, search="", locations=(), positions=(),
                    statuses=(), tags=(), companies=(), email_only=False, no_email=False) -> int:
    ids_query = _filtered_lead_ids_query(session, search, locations, positions, statuses, tags,
                                         companies=companies, email_only=email_only, no_email=no_email)
    result = session.execute(
        update(Lead)
        .where(Lead.id.in_(ids_query))
        .values(status=new_status, updated_at=_utcnow())
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return result.rowcount or 0


def bulk_add_tags(session: Session, new_tags: list, search="", locations=(), positions=(),
                  statuses=(), tags=(), companies=(), email_only=False, no_email=False) -> int:
    ids_query = _filtered_lead_ids_query(session, search, locations, positions, statuses, tags,
                                         companies=companies, email_only=email_only, no_email=no_email)
    now = _utcnow()
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

    return len(payload)


# ── Writes: CSV import ───────────────────────────────────────────────────────

def import_leads(session: Session, records: list, tags: list, industry: str | None = None) -> dict:
    industry = (industry or "").strip()
    valid = [r for r in records if r]
    skipped_invalid = len(records) - len(valid)

    if not valid:
        return {"added": 0, "skipped_duplicates": 0,
                "skipped_invalid": skipped_invalid,
                "industry_set": 0, "industry_kept": 0}

    tag_value = ",".join(sorted(set(tags))) if tags else None
    emails = [r["email"] for r in valid if r.get("email")]

    existing = set()
    if emails:
        existing = set(session.execute(
            select(Lead.email).where(Lead.email.in_(emails))
        ).scalars().all())

    to_add, seen = [], set()
    for record in valid:
        email = record.get("email")
        if email and (email in existing or email in seen):
            continue
        if email:
            seen.add(email)
        to_add.append(dict(record))

    name_domains = {}
    for record in to_add:
        domain = _normalize_domain(record.get("company_domain"))
        name = record.get("company_name") or domain
        if not name:
            continue
        record["company_name"] = name
        if name not in name_domains or (domain and not name_domains[name]):
            name_domains[name] = domain

    companies = _get_or_create_companies(session, name_domains)

    industry_set = industry_kept = 0
    if industry:
        for company in {c.id: c for c in companies.values()}.values():
            current = (company.industry or "").strip()
            if not current:
                company.industry = industry
                industry_set += 1
            elif current.lower() != industry.lower():
                industry_kept += 1

    location_pairs = []
    for record in to_add:
        record.pop("company_domain", None)
        company_name = record.pop("company_name", None)
        if company_name:
            company = companies[company_name]
            record["company_id"] = company.id
            location_pairs.append((company, record.get("location")))
        if tag_value:
            record["tags"] = tag_value

    _append_company_locations(location_pairs)
    session.add_all(Lead(**record) for record in to_add)
    session.commit()

    return {
        "added": len(to_add),
        "skipped_duplicates": len(valid) - len(to_add),
        "skipped_invalid": skipped_invalid,
        "industry_set": industry_set,
        "industry_kept": industry_kept,
    }
