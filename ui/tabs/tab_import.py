"""
📥 Import tab: CSV upload with fuzzy column detection and BATCHED insert
(one duplicate pre-check, one company batch, one commit — see
db.queries.import_leads).

Fixes vs. the old dashboard: guarded pd.read_csv, no NameError when the save
button is clicked before uploading, and results are reported after the import
actually succeeds (they used to be printed from a `finally` block even on
failure).
"""

import pandas as pd
import streamlit as st

from db import queries
from ui.constants import AVAILABLE_TAGS

# Recognized CSV header variants (normalized: lowercase, spaces→underscores).
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


def _df_to_records(df: pd.DataFrame, mapping: dict) -> list:
    """DataFrame → list of clean lead dicts ('company' becomes 'company_name').
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


def render():
    st.header("Importuj nowe kontakty")
    st.markdown("Wgraj plik CSV (np. z Eventory lub Livespace), aby dodać rekordy do bazy.")

    uploaded_file = st.file_uploader("Przeciągnij i upuść plik CSV tutaj", type=["csv"])

    df = None
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"Nie udało się wczytać pliku CSV: {e}")
        else:
            st.success(f"Pomyślnie wczytano plik: {uploaded_file.name}")
            st.markdown(f"**Podgląd pierwszych 5 wierszy z {len(df)}**")
            st.dataframe(df.head())

    selected_tags = st.multiselect(
        "Przypisz tagi do importowanych leadów:",
        options=AVAILABLE_TAGS,
        placeholder="Opcjonalne — wybierz tagi dla tej partii importu",
        key="import_tags",
    )

    if not st.button("Zapisz do bazy PostgreSQL", type="primary"):
        return

    if df is None or df.empty:
        st.error("Proszę najpierw wczytać plik CSV")
        return

    mapping = detect_column_mapping(df.columns)
    if not mapping or "email" not in mapping:
        st.error("CSV musi zawierac kolumne 'email' (lub podobnie nazwana)")
        return

    st.info(f"Wykryto kolumny: {mapping}")
    records = _df_to_records(df, mapping)

    try:
        with st.spinner(f"Importuję {len(records)} rekordów..."):
            summary = queries.import_leads(records, selected_tags)
    except Exception as e:
        st.error(f"Import nie powiódł się — żadne dane nie zostały zapisane: {e}")
        return

    if summary["added"]:
        st.success(f"Pomyslnie dodano {summary['added']} lead(ow)")
    if summary["skipped_duplicates"]:
        st.warning(f"Pominieto {summary['skipped_duplicates']} lead(ow) (duplikaty)")
    if summary["skipped_invalid"]:
        st.warning(f"Pominieto {summary['skipped_invalid']} wiersz(y) bez adresu email")
    if not summary["added"]:
        st.info("Nie dodano żadnych nowych rekordów.")
