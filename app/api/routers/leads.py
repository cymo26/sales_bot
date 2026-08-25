"""Lead endpoints — Kontakty tab + Lead Profile modal + Quick Add modal."""

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api import service
from app.api.deps import get_db
from app.api.schemas import (
    BulkActionOut, BulkDeleteIn, BulkDeleteOut, BulkStatusIn, BulkTagsIn,
    IndustryConflict, LeadDetailOut, LeadFilterOptionsOut, LeadMetricsOut,
    LeadOut, LeadUpdateIn, LeadUpdateOut, LeadsCreateIn, LeadsCreateResultOut,
    LeadsPageOut, PageMeta,
)

router = APIRouter(prefix="/api/leads", tags=["leads"])


def _filters(
    search: str = "",
    locations: list[str] = Query(default=[]),
    positions: list[str] = Query(default=[]),
    statuses: list[str] = Query(default=[]),
    tags: list[str] = Query(default=[]),
    companies: list[str] = Query(default=[]),
    email_only: bool = False,
    no_email: bool = False,
) -> dict:
    return {
        "search": search, "locations": locations, "positions": positions,
        "statuses": statuses, "tags": tags, "companies": companies,
        "email_only": email_only, "no_email": no_email,
    }


@router.get("", response_model=LeadsPageOut)
def list_leads(page: int = 1, filters: dict = Depends(_filters), db: Session = Depends(get_db)):
    data = service.fetch_leads_page(db, page=page, **filters)
    return {
        "rows": data["rows"],
        "meta": {"page": data["page"], "pages": data["pages"], "total": data["total"]},
    }


@router.get("/metrics", response_model=LeadMetricsOut)
def lead_metrics(filters: dict = Depends(_filters), db: Session = Depends(get_db)):
    return service.fetch_lead_metrics(db, **filters)


@router.get("/filter-options", response_model=LeadFilterOptionsOut)
def lead_filter_options(
    search: str = "",
    locations: list[str] = Query(default=[]),
    positions: list[str] = Query(default=[]),
    statuses: list[str] = Query(default=[]),
    companies: list[str] = Query(default=[]),
    email_only: bool = False,
    no_email: bool = False,
    db: Session = Depends(get_db),
):
    return service.fetch_lead_filter_options(
        db, search=search, locations=locations, positions=positions,
        statuses=statuses, companies=companies, email_only=email_only, no_email=no_email,
    )


@router.get("/export")
def export_leads(filters: dict = Depends(_filters), db: Session = Depends(get_db)):
    rows = service.fetch_leads_for_export(db, **filters)
    csv_bytes = pd.DataFrame(rows, columns=["Name", "Email", "Position"]).to_csv(index=False).encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=apple_script_outreach.csv"},
    )


@router.get("/{lead_id}", response_model=LeadDetailOut)
def get_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = service.fetch_lead_detail(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono kontaktu.")
    return lead


@router.patch("/{lead_id}", response_model=LeadUpdateOut)
def update_lead(lead_id: str, body: LeadUpdateIn, db: Session = Depends(get_db)):
    changed = service.update_lead(db, lead_id, body.status, body.notes)
    return {"changed": changed}


@router.delete("/{lead_id}", response_model=BulkDeleteOut)
def delete_lead(lead_id: str, db: Session = Depends(get_db)):
    deleted = service.delete_leads(db, [lead_id])
    return {"deleted": deleted}


@router.post("/bulk-delete", response_model=BulkDeleteOut)
def bulk_delete(body: BulkDeleteIn, db: Session = Depends(get_db)):
    return {"deleted": service.delete_leads(db, body.ids)}


@router.post("/bulk-tags", response_model=BulkActionOut)
def bulk_tags(body: BulkTagsIn, db: Session = Depends(get_db)):
    updated = service.bulk_add_tags(db, body.tags, **body.filters.model_dump())
    return {"updated": updated}


@router.post("/bulk-status", response_model=BulkActionOut)
def bulk_status(body: BulkStatusIn, db: Session = Depends(get_db)):
    updated = service.bulk_set_status(db, body.status, **body.filters.model_dump())
    return {"updated": updated}


@router.post("", response_model=LeadsCreateResultOut)
def create_leads(body: LeadsCreateIn, db: Session = Depends(get_db)):
    leads = [ld.model_dump() for ld in body.leads]

    # --- Validate uniqueness of email within the batch, mirroring the dialog ---
    for ld in leads:
        ld["email"] = ld["email"].strip()
        ld["company_name"] = ld["company_name"].strip()

    # --- Dry run: does any existing company have a DIFFERENT industry? ---
    company_industries = {}
    for ld in leads:
        if ld.get("company_industry"):
            company_industries.setdefault(ld["company_name"], ld["company_industry"])
    conflicts = service.preview_industry_conflicts(db, company_industries)

    unresolved = [
        c for c in conflicts
        if body.conflict_resolutions.get(c["company"]) not in ("keep", "overwrite")
    ]
    if unresolved:
        raise HTTPException(
            status_code=409,
            detail={"conflicts": [IndustryConflict(**c).model_dump() for c in conflicts]},
        )

    for ld in leads:
        if body.conflict_resolutions.get(ld["company_name"]) == "keep":
            ld["company_industry"] = None

    result = service.create_leads(db, leads)
    return result
