"""
"Profil Kontaktu" dialog: full lead details with inline status/notes editing.

Open it by bumping nothing — just call show_lead_dialog(lead_id) when the
row's "Szczegóły" button returns True.
"""

import streamlit as st

from db import queries
from ui.components import render_tags
from ui.constants import STATUS_OPTIONS, TAB_FIRMY, status_label


@st.dialog("Profil Kontaktu", width="large")
def show_lead_dialog(lead_id: str):
    try:
        lead = queries.fetch_lead_detail(lead_id)
    except Exception as e:
        st.error(f"Błąd przy pobieraniu kontaktu: {e}")
        return
    if lead is None:
        st.error("Nie znaleziono kontaktu.")
        return

    # --- Header ---
    col_name, col_ln = st.columns([5, 1])
    col_name.subheader(lead["full_name"])
    if lead["linkedin_url"]:
        col_ln.link_button("🔗 LinkedIn", lead["linkedin_url"], use_container_width=True)

    st.caption(f"{lead['position']}  ·  {lead['company']}")

    if lead["tags"]:
        st.markdown(render_tags(lead["tags"]), unsafe_allow_html=True)

    st.markdown("---")

    # --- Details ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Email", lead["email"])
    col2.metric("Firma", lead["company"])
    col3.metric("Lokalizacja", lead["location"])

    # Cross-navigation: close the dialog, switch to Baza Firm with the search
    # filter pre-set to this company's name, so only it shows up — expanded.
    if lead["company_id"] and col2.button(
        "🏢 Przejdź do profilu firmy",
        key=f"goto_company_{lead_id}",
        use_container_width=True,
    ):
        st.session_state["auto_expand_company_id"] = lead["company_id"]
        st.session_state["active_tab"] = TAB_FIRMY
        st.session_state["applied_filters_f"] = {"search": lead["company"]}
        # Bump the widget-key generation so the search box shows the new value.
        st.session_state["fk_reset_f"] = st.session_state.get("fk_reset_f", 0) + 1
        st.session_state["page_firmy"] = 1
        st.rerun()

    col4, col5, col6 = st.columns(3)
    col4.metric("Status", status_label(lead["status"]))
    col5.metric("Branza firmy", lead["industry"] or "—")
    col6.metric("Wielkosc firmy", lead["size_range"] or "—")

    st.markdown("---")

    # --- Editable section ---
    st.markdown("**Edytuj rekord**")
    new_status = st.selectbox(
        "Status",
        options=STATUS_OPTIONS,
        index=STATUS_OPTIONS.index(lead["status"]) if lead["status"] in STATUS_OPTIONS else 0,
        format_func=status_label,
        key=f"dialog_status_{lead_id}",
    )
    new_notes = st.text_area(
        "Notatki",
        value=lead["notes"],
        height=120,
        max_chars=500,
        placeholder="Wpisz swoje notatki operacyjne…",
        key=f"dialog_notes_{lead_id}",
    )

    st.markdown("---")
    col_save, _ = st.columns([1, 4])
    if col_save.button("Zapisz zmiany", type="primary", key=f"dialog_save_{lead_id}"):
        try:
            changed = queries.update_lead(lead_id, new_status, new_notes)
        except Exception as e:
            st.error(f"Nie udało się zapisać zmian: {e}")
            return
        st.toast("Zmiany zapisane!" if changed else "Brak zmian do zapisania.")
        # Outside any try/except — st.rerun() raises RerunException by design.
        st.rerun()
