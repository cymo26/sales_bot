"""CSV column detection + row extraction for the Import endpoint — ported
verbatim from ui/tabs/tab_import.py, just without the Streamlit calls."""

import pandas as pd

_COLUMN_PATTERNS = {
    "email": [
        "work_email", "work_e_mail", "email", "e_mail", "e-mail", "mail",
        "emailaddress", "email_address",
    ],
    "first_name": [
        "first_name", "firstname", "first", "name_first", "imie",
        "given_name", "forename",
    ],
    "last_name": [
        "last_name", "lastname", "last", "surname", "name_last", "nazwisko",
        "family_name",
    ],
    "position": [
        "job_title", "jobtitle", "job", "title", "role", "stanowisko",
        "headline", "position",
    ],
    "company": [
        "company_name", "companyname", "company", "firma", "organisation",
        "organization", "employer", "organization_name",
    ],
    "company_domain": [
        "company_domain", "companydomain", "domain", "company_website",
        "website",
    ],
    "location": [
        "city", "miasto", "lokalizacja", "location", "loc", "region", "kraj",
        "country", "address",
    ],
    "linkedin_url": [
        "linkedin_url", "linkedin", "linkedin_profile", "profile_url",
        "profile", "li_url", "li_profile", "social", "link",
    ],
}


def detect_column_mapping(df_columns) -> dict:
    """Map CSV columns to Lead fields, tolerating naming variations."""
    normalized = {col.lower().replace(" ", "_"): col for col in df_columns}
    mapping = {}
    for field, patterns in _COLUMN_PATTERNS.items():
        for pattern in patterns:
            if pattern in normalized:
                mapping[field] = normalized[pattern]
                break
    return mapping


def df_to_records(df: pd.DataFrame, mapping: dict) -> list:
    """DataFrame -> list of clean lead dicts ('company' becomes 'company_name').
    Skips empty cells and '❌' error markers from scraping tools."""
    records = []
    for _, row in df.iterrows():
        record = {}
        for field, csv_col in mapping.items():
            value = row[csv_col]
            if pd.isna(value) or str(value).startswith("❌"):
                continue
            value = str(value).strip()
            if not value:
                continue
            record["company_name" if field == "company" else field] = value
        records.append(record)
    return records
