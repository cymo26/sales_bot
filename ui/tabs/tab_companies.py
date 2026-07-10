"""
🏢 Baza Firm tab: account-based view, paginated at the COMPANY level
(20/page — leads nest inside expanders, so the row budget stays bounded).

Location options now come from Company.location (they were wrongly built from
lead locations before, making some companies unfilterable).
"""

import streamlit as st

from db import queries
from ui.components import (current_page, render_lead_row,
                           render_lead_table_header, render_pagination,
                           reset_page)
from ui.constants import AVAILABLE_TAGS
from ui.dialogs import show_lead_dialog

_PAGE_KEY = "page_firmy"


def render():
    st.header("Baza Firm (Account-Based View)")

    # ── Staged filter state ──
    st.session_state.setdefault("applied_filters_f", {})
    st.session_state.setdefault("fk_reset_f", 0)
    applied = st.session_state["applied_filters_f"]
    reset_key = st.session_state["fk_reset_f"]

    search = applied.get("search", "")
    f_locations = applied.get("location", [])
    f_tags = applied.get("tags", [])

    try:
        location_options = queries.fetch_company_locations()
    except Exception as e:
        st.error(f"Błąd przy pobieraniu lokalizacji: {e}")
        return
    f_locations = [v for v in f_locations if v in location_options]

    # ── Filter bar ──
    col_search, col_loc, col_tags = st.columns([3, 2, 2])
    col_search.text_input(
        "Szukaj po nazwie firmy", value=search, placeholder="np. Acme, Comarch...",
        key=f"f_search_f_{reset_key}", label_visibility="collapsed",
    )
    col_loc.multiselect(
        "Lokalizacja", options=location_options, default=f_locations,
        placeholder="Lokalizacja", key=f"f_location_f_{reset_key}",
        label_visibility="collapsed",
    )
    col_tags.multiselect(
        "Filtruj po tagu", options=AVAILABLE_TAGS, default=f_tags,
        placeholder="Filtruj po tagu", key=f"f_tags_f_{reset_key}",
        label_visibility="collapsed",
    )

    col_save, col_clear = st.columns([1.5, 1.5])
    if col_save.button("Zapisz filtry", type="primary", use_container_width=True,
                       key="btn_save_filters_f"):
        st.session_state["applied_filters_f"] = {
            "search":   st.session_state.get(f"f_search_f_{reset_key}", ""),
            "location": st.session_state.get(f"f_location_f_{reset_key}", []),
            "tags":     st.session_state.get(f"f_tags_f_{reset_key}", []),
        }
        reset_page(_PAGE_KEY)
        st.rerun()
    if col_clear.button("Wyczyść filtry", use_container_width=True,
                        key="btn_clear_filters_f"):
        st.session_state["applied_filters_f"] = {}
        st.session_state["fk_reset_f"] = reset_key + 1
        reset_page(_PAGE_KEY)
        st.rerun()

    # ── Data: one page of companies with nested (tag-filtered) leads ──
    try:
        page_data = queries.fetch_companies_page(
            page=current_page(_PAGE_KEY),
            search=search,
            locations=tuple(f_locations),
            tags=tuple(f_tags),
        )
    except Exception as e:
        st.error(f"Błąd przy pobieraniu firm: {e}")
        return

    companies = page_data["rows"]
    if not companies:
        if search or f_locations or f_tags:
            st.info("Brak firm pasujących do filtrów.")
        else:
            st.info("Brak firm w bazie danych.")
        return

    st.caption(f"Znaleziono **{page_data['total']}** firm(y).")

    # Cross-navigation from the lead profile: expand the target company once.
    auto_expand_id = st.session_state.get("auto_expand_company_id")

    for co in companies:
        is_expanded = co["id"] == auto_expand_id
        label = f"{co['name']} — {co['domain']}  ·  {len(co['leads'])} kontakt(ów)"
        with st.expander(label, expanded=is_expanded):
            meta1, meta2, meta3 = st.columns(3)
            meta1.markdown(f"**Branża:** {co['industry']}")
            meta2.markdown(f"**Lokalizacja:** {co['location']}")
            meta3.markdown(f"**Wielkość:** {co['size_range']}")

            if co["leads"]:
                st.markdown("**Kontakty w tej firmie:**")
                render_lead_table_header()
                for row in co["leads"]:
                    if render_lead_row(row, key_prefix="co_"):
                        show_lead_dialog(row["id"])
            else:
                st.caption("Brak kontaktów pasujących do filtrów.")

    # One-shot: clear after rendering so the expander doesn't stay pinned open
    # (or pop open again) on subsequent reruns.
    if auto_expand_id:
        st.session_state.pop("auto_expand_company_id", None)

    st.markdown("---")
    render_pagination(_PAGE_KEY, page_data["page"], page_data["pages"],
                      page_data["total"], "firm")
