"""Company endpoints — Baza Firm tab (account-based, nested leads)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import service
from app.api.deps import get_db

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("")
def list_companies(
    page: int = 1,
    search: str = "",
    locations: list[str] = Query(default=[]),
    tags: list[str] = Query(default=[]),
    db: Session = Depends(get_db),
):
    data = service.fetch_companies_page(db, page=page, search=search, locations=locations, tags=tags)
    return {
        "rows": data["rows"],
        "meta": {"page": data["page"], "pages": data["pages"], "total": data["total"]},
    }


@router.get("/locations", response_model=list[str])
def company_locations(db: Session = Depends(get_db)):
    return service.fetch_company_locations(db)


@router.get("/industries", response_model=list[str])
def industries(db: Session = Depends(get_db)):
    return service.fetch_industries(db)
