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
from ui.constants import ALL_TABS, TAB_FIRMY, TAB_IMPORT, TAB_KONTAKTY
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

    # Session-state-driven navigation (st.tabs cannot be switched from code).
    # Anything may set st.session_state["active_tab"] before st.rerun() to
    # navigate — e.g. the lead profile's "Przejdź do profilu firmy" button.
    # Only the active view renders, which also cuts rerun work by two thirds.
    st.session_state.setdefault("active_tab", TAB_KONTAKTY)
    selection = st.segmented_control(
        "Nawigacja", ALL_TABS, key="active_tab", label_visibility="collapsed"
    )
    if selection:
        st.session_state["_last_tab"] = selection
    # Clicking the active segment deselects it (returns None) — keep showing
    # the last real selection instead of jumping to the default view.
    active = selection or st.session_state.get("_last_tab", TAB_KONTAKTY)

    if active == TAB_FIRMY:
        tab_companies.render()
    elif active == TAB_IMPORT:
        tab_import.render()
    else:
        tab_contacts.render()


main()
