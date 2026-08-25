"""Pydantic request/response models — the HTTP contract for the React app.

Field-naming note: db/queries.py's `_lead_row()` returned pre-formatted
display strings (e.g. "—" placeholders, a concatenated `full_name`). Here the
API returns raw, nullable fields instead and lets the frontend format them —
that's a presentation-layer relocation, not a behavior change; every value
that was displayed still round-trips through the API unchanged.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ── Leads ────────────────────────────────────────────────────────────────────

class LeadOut(BaseModel):
    id: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    position: str | None = None
    company_id: str | None = None
    company_name: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    tags: list[str] = []
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    livespace_owner_name: str | None = None
    livespace_deal_name: str | None = None
    livespace_sync_status: str | None = None
    livespace_last_synced_at: datetime | None = None
    company_livespace_engaged: bool = False
    company_livespace_engaged_via: str | None = None


class LeadDetailOut(LeadOut):
    industry: str | None = None
    size_range: str | None = None


class PageMeta(BaseModel):
    page: int
    pages: int
    total: int


class LeadsPageOut(BaseModel):
    rows: list[LeadOut]
    meta: PageMeta


class LeadMetricsOut(BaseModel):
    total: int
    new: int
    companies: int
    with_position: int


class LeadFilterOptionsOut(BaseModel):
    locations: list[str]
    positions: list[str]
    statuses: list[str]
    companies: list[str]


class LeadFilters(BaseModel):
    """Same shape used to build GET query params and POST bulk-action bodies."""
    search: str = ""
    locations: list[str] = []
    positions: list[str] = []
    statuses: list[str] = []
    tags: list[str] = []
    companies: list[str] = []
    email_only: bool = False
    no_email: bool = False


class LeadCreateIn(BaseModel):
    first_name: str
    last_name: str
    email: str
    company_name: str
    company_industry: str | None = None
    position: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    status: str = "new"
    tags: list[str] = []


class LeadsCreateIn(BaseModel):
    leads: list[LeadCreateIn] = Field(..., min_length=1, max_length=5)
    # Set only when re-submitting after the caller resolved industry
    # conflicts returned by a first attempt's 409 response. Maps company
    # name -> "keep" (drop the incoming industry) | "overwrite" (apply it).
    conflict_resolutions: dict[str, str] = {}


class IndustryConflict(BaseModel):
    company: str
    current: str
    incoming: str


class LeadsCreateResultOut(BaseModel):
    added: int
    skipped: list[str]


class LeadUpdateIn(BaseModel):
    status: str
    notes: str | None = None


class LeadUpdateOut(BaseModel):
    changed: bool


class BulkDeleteIn(BaseModel):
    ids: list[str]


class BulkDeleteOut(BaseModel):
    deleted: int


class BulkTagsIn(BaseModel):
    tags: list[str]
    filters: LeadFilters = LeadFilters()


class BulkStatusIn(BaseModel):
    status: str
    filters: LeadFilters = LeadFilters()


class BulkActionOut(BaseModel):
    updated: int


# ── Companies ────────────────────────────────────────────────────────────────

class CompanyOut(BaseModel):
    id: str
    name: str
    domain: str | None = None
    industry: str | None = None
    location: str | None = None
    size_range: str | None = None
    livespace_engaged: bool = False
    livespace_engaged_via: str | None = None
    leads: list[LeadOut]


class CompaniesPageOut(BaseModel):
    rows: list[CompanyOut]
    meta: PageMeta


# ── Livespace ────────────────────────────────────────────────────────────────

class LivespaceRefreshOut(BaseModel):
    livespace_sync_status: str | None = None
    livespace_owner_name: str | None = None
    livespace_deal_name: str | None = None
    livespace_last_synced_at: datetime | None = None
    company_livespace_engaged: bool = False
    company_livespace_engaged_via: str | None = None


# ── Import ───────────────────────────────────────────────────────────────────

class ImportFileReport(BaseModel):
    filename: str
    rows: int
    detected_columns: dict[str, str] = {}
    missing_email_column: bool = False
    error: str | None = None


class ImportResultOut(BaseModel):
    added: int
    skipped_duplicates: int
    skipped_invalid: int
    industry_set: int
    industry_kept: int
    files: list[ImportFileReport]
