"""
SALES BOT — PROIDEA · entry point / router.

Run with:  streamlit run ui/dashboard.py

This file only wires things together. The real logic lives in:
    ui/styles.py      — CSS theme
    ui/constants.py   — statuses, tags, display labels
    ui/components.py  — shared lead table + pagination
    ui/dialogs/       — Quick Add & Profil Kontaktu dialogs
    ui/tabs/          — the three tab views
    db/queries.py     — all SQL (paginated fetches, batched writes)
"""

import os
import sys

# Make the project root importable before any project imports.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st

# Must be the first Streamlit command — keep ahead of project imports.
st.set_page_config(page_title="SALES BOT", layout="wide")

from db import queries
from ui.styles import apply_custom_css
from ui.tabs import tab_companies, tab_contacts, tab_import


def main() -> None:
    apply_custom_css()
    st.title("SALES BOT")

    # One-shot per process: pool warm-up, unaccent extension,
    # legacy Polish→canonical status migration.
    try:
        queries.bootstrap()
    except Exception as e:
        st.error(f"Nie można połączyć się z bazą danych: {e}")
        st.stop()

    tab_kontakty, tab_firmy, tab_imp = st.tabs(
        ["👥 Kontakty", "🏢 Baza Firm", "📥 Import"]
    )
    with tab_kontakty:
        tab_contacts.render()
    with tab_firmy:
        tab_companies.render()
    with tab_imp:
        tab_import.render()


main()
