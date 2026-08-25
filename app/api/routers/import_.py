"""Import endpoint — 📥 Import Danych tab. Accepts up to 5 CSV files in one
multipart request; column detection + the batched insert run per request,
mirroring ui/tabs/tab_import.py exactly (one duplicate pre-check, one company
batch, one commit per file — see app.api.service.import_leads)."""

import io

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api import service
from app.api.csv_utils import detect_column_mapping, df_to_records
from app.api.deps import get_db
from app.api.schemas import ImportFileReport, ImportResultOut

router = APIRouter(prefix="/api/import", tags=["import"])

_MAX_FILES = 5


@router.post("", response_model=ImportResultOut)
async def import_csv(
    files: list[UploadFile] = File(...),
    tags: list[str] = Form(default=[]),
    industry: str = Form(default=""),
    db: Session = Depends(get_db),
):
    files = files[:_MAX_FILES]
    industry = (industry or "").strip()

    all_records: list[dict] = []
    file_reports: list[ImportFileReport] = []

    for upload in files:
        content = await upload.read()
        try:
            df = pd.read_csv(io.BytesIO(content))
        except Exception as e:
            file_reports.append(ImportFileReport(
                filename=upload.filename, rows=0, error=f"Nie udało się wczytać pliku: {e}",
            ))
            continue
        if df.empty:
            file_reports.append(ImportFileReport(
                filename=upload.filename, rows=0, error="Plik jest pusty — pominięto.",
            ))
            continue

        mapping = detect_column_mapping(df.columns)
        if not mapping:
            file_reports.append(ImportFileReport(
                filename=upload.filename, rows=len(df),
                error="Nie rozpoznano żadnej kolumny — plik pominięty.",
            ))
            continue

        file_reports.append(ImportFileReport(
            filename=upload.filename,
            rows=len(df),
            detected_columns=mapping,
            missing_email_column="email" not in mapping,
        ))
        all_records.extend(df_to_records(df, mapping))

    if not all_records:
        return ImportResultOut(
            added=0, skipped_duplicates=0, skipped_invalid=0,
            industry_set=0, industry_kept=0, files=file_reports,
        )

    summary = service.import_leads(db, all_records, tags, industry)
    return ImportResultOut(**summary, files=file_reports)
