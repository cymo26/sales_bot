"""
👥 Kontakty tab: staged filters, summary metrics, bulk actions, CSV export
and the paginated lead table (max 50 rows per page, SQL-side).

Error-handling rule for the whole tab: try/except wraps DB calls ONLY, and
every st.rerun() sits outside try blocks (st.rerun raises RerunException,
which a broad except would swallow — the old dashboard's worst bug).
"""

import pandas as pd
import streamlit as st

from db import queries
from ui.components import (current_page, render_lead_row,
                           render_lead_table_header, render_pagination,
                           reset_page)
from ui.constants import AVAILABLE_TAGS, STATUS_OPTIONS, status_label
from ui.dialogs import show_add_leads_dialog, show_lead_dialog

_PAGE_KEY = "page_kontakty"


def render():
    col_title, col_del_btn = st.columns([5, 1])
    col_title.header("Twoje Kontakty")

    # ── Staged filter state — applied only on "Zapisz filtry" ──
    st.session_state.setdefault("applied_filters", {})
    st.session_state.setdefault("fk_reset", 0)
    applied = st.session_state["applied_filters"]
    reset_key = st.session_state["fk_reset"]

    search = applied.get("search", "")
    f_locations = applied.get("location", [])
    f_statuses = applied.get("status", [])
    f_positions = applied.get("position", [])
    f_tags = applied.get("tags", [])

    # ── Data (all SQL-side: cascading options, aggregates, one page of rows) ──
    try:
        options = queries.fetch_lead_filter_options(
            search=search,
            locations=tuple(f_locations),
            positions=tuple(f_positions),
            statuses=tuple(f_statuses),
        )
        # Drop applied values that no longer exist in the data
        f_locations = [v for v in f_locations if v in options["locations"]]
        f_positions = [v for v in f_positions if v in options["positions"]]
        f_statuses = [v for v in f_statuses if v in options["statuses"]]

        filters = {
            "search": search,
            "locations": tuple(f_locations),
            "positions": tuple(f_positions),
            "statuses": tuple(f_statuses),
            "tags": tuple(f_tags),
        }
        metrics = queries.fetch_lead_metrics(**filters)
        page_data = queries.fetch_leads_page(page=current_page(_PAGE_KEY), **filters)
    except Exception as e:
        st.error(f"Blad przy pobieraniu danych: {e}")
        return

    rows = page_data["rows"]

    # ── Active filter badges ──
    active = []
    if search:      active.append(f"Szukaj: *{search}*")
    if f_locations: active.append(f"Lokalizacja: *{', '.join(f_locations)}*")
    if f_statuses:  active.append(f"Status: *{', '.join(status_label(s) for s in f_statuses)}*")
    if f_positions: active.append(f"Stanowisko: *{', '.join(f_positions)}*")
    if f_tags:      active.append(f"Tagi: *{', '.join(f_tags)}*")
    if active:
        st.caption("Aktywne filtry: " + " | ".join(active))

    # ── Bulk delete (header button) ──
    # Selection only ever counts rows visible on the current page; checkboxes
    # of rows that scrolled out of view get cleared so they can't come back
    # checked after a filter change and be deleted by surprise.
    visible_ids = [r["id"] for r in rows]
    for lead_id in set(st.session_state.get("_kontakty_visible", [])) - set(visible_ids):
        st.session_state.pop(f"del_{lead_id}", None)
    st.session_state["_kontakty_visible"] = visible_ids

    pending = [i for i in visible_ids if st.session_state.get(f"del_{i}", False)]
    label = f"Usuń zaznaczone ({len(pending)})" if pending else "Usuń zaznaczone"
    if col_del_btn.button(label, type="primary", disabled=not pending, key="bulk_delete_btn"):
        try:
            deleted = queries.delete_leads(pending)
        except Exception as e:
            st.error(f"Nie udało się usunąć kontaktów: {e}")
        else:
            for lead_id in pending:
                st.session_state.pop(f"del_{lead_id}", None)
            st.toast(f"Usunięto {deleted} kontakt(ów).")
            st.rerun()

    # ── Summary metrics — SQL aggregates over the WHOLE filtered set ──
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Lacznie", metrics["total"])
    col2.metric("Nowe", metrics["new"])
    col3.metric("Firmy", metrics["companies"])
    col4.metric("Ze stanowiskiem", metrics["with_position"])

    # ── Filter bar (staged) ──
    col_search, col_loc, col_pos, col_status, col_tags = st.columns([2.5, 1.5, 2, 1.5, 1.5])
    col_search.text_input(
        "Szukaj", value=search, placeholder="Imię nazwisko, email, firma...",
        key=f"f_search_{reset_key}", label_visibility="collapsed",
    )
    col_loc.multiselect(
        "Lokalizacja", options=options["locations"], default=f_locations,
        placeholder="Lokalizacja", key=f"f_location_{reset_key}",
        label_visibility="collapsed",
    )
    col_pos.multiselect(
        "Stanowisko", options=options["positions"], default=f_positions,
        placeholder="Stanowisko", key=f"f_position_{reset_key}",
        label_visibility="collapsed",
    )
    col_status.multiselect(
        "Status", options=options["statuses"], default=f_statuses,
        format_func=status_label, placeholder="Status",
        key=f"f_status_{reset_key}", label_visibility="collapsed",
    )
    col_tags.multiselect(
        "Tagi", options=AVAILABLE_TAGS, default=f_tags, placeholder="Tagi",
        key=f"f_tags_{reset_key}", label_visibility="collapsed",
    )

    col_save, col_clear, col_export = st.columns([1.5, 1.5, 1])
    if col_save.button("Zapisz filtry", type="primary", use_container_width=True,
                       key="btn_save_filters"):
        st.session_state["applied_filters"] = {
            "search":   st.session_state.get(f"f_search_{reset_key}", ""),
            "location": st.session_state.get(f"f_location_{reset_key}", []),
            "status":   st.session_state.get(f"f_status_{reset_key}", []),
            "position": st.session_state.get(f"f_position_{reset_key}", []),
            "tags":     st.session_state.get(f"f_tags_{reset_key}", []),
        }
        reset_page(_PAGE_KEY)
        st.rerun()
    if col_clear.button("Wyczyść filtry", use_container_width=True,
                        key="btn_clear_filters"):
        st.session_state["applied_filters"] = {}
        st.session_state["fk_reset"] = reset_key + 1
        st.session_state.pop("_export_kontakty", None)
        reset_page(_PAGE_KEY)
        st.rerun()

    # ── CSV export — two-step so the full set is only queried on demand ──
    fingerprint = tuple(sorted((k, tuple(v) if isinstance(v, (list, tuple)) else v)
                               for k, v in filters.items()))
    stash = st.session_state.get("_export_kontakty")
    if stash and stash["fp"] == fingerprint:
        col_export.download_button(
            label=f"Pobierz CSV ({stash['count']})", data=stash["csv"],
            file_name="apple_script_outreach.csv", mime="text/csv",
            use_container_width=True,
        )
    else:
        if col_export.button(f"Eksportuj CSV ({metrics['total']})",
                             use_container_width=True, key="btn_export",
                             disabled=metrics["total"] == 0):
            try:
                export_rows = queries.fetch_leads_for_export(**filters)
            except Exception as e:
                st.error(f"Eksport nie powiódł się: {e}")
            else:
                st.session_state["_export_kontakty"] = {
                    "fp": fingerprint,
                    "count": len(export_rows),
                    "csv": pd.DataFrame(export_rows).to_csv(index=False).encode("utf-8"),
                }
                st.rerun()

    # ── Empty state ──
    if not rows:
        if search or f_locations or f_statuses or f_positions or f_tags:
            st.info("Brak wyników dla aktualnych filtrów. Zmień kryteria lub wyczyść filtry.")
        else:
            st.info("Brak leadów w bazie danych. Zaimportuj dane w zakładce 'Import'.")
        if st.button("Dodaj leada", use_container_width=True, key="btn_add_lead"):
            st.session_state["add_dialog_gen"] = st.session_state.get("add_dialog_gen", 0) + 1
            show_add_leads_dialog()
        return

    st.markdown("---")

    # ── Bulk actions — apply to ALL filtered leads, not just this page ──
    with st.expander("Oznacz leada", expanded=False):
        st.caption(f"Akcje dotyczą wszystkich przefiltrowanych leadów — obecnie **{metrics['total']}**.")

        # — Tagi —
        ma_col, ma_btn_col = st.columns([4, 1])
        bulk_tags = ma_col.multiselect(
            "Dodaj tagi", options=AVAILABLE_TAGS,
            placeholder="Wybierz tagi do przypisania...",
            key="bulk_tags", label_visibility="collapsed",
        )
        if ma_btn_col.button(f"Przypisz tagi ({metrics['total']})", type="primary",
                             key="bulk_tag_btn", disabled=not bulk_tags,
                             use_container_width=True):
            try:
                updated = queries.bulk_add_tags(bulk_tags, **filters)
            except Exception as e:
                st.error(f"Nie udało się przypisać tagów: {e}")
            else:
                st.toast(f"Tagi {', '.join(sorted(bulk_tags))} przypisane do {updated} leadów.")
                st.rerun()

        st.markdown("<hr style='margin:8px 0;border-color:rgba(255,255,255,.07)'>",
                    unsafe_allow_html=True)

        # — Status —
        ms_col, ms_btn_col = st.columns([4, 1])
        bulk_status = ms_col.selectbox(
            "Zmień status", options=[""] + STATUS_OPTIONS, index=0,
            format_func=lambda s: "Wybierz nowy status dla wszystkich..." if s == "" else status_label(s),
            key="bulk_status", label_visibility="collapsed",
        )
        if ms_btn_col.button(f"Zmień status ({metrics['total']})", type="primary",
                             key="bulk_status_btn", disabled=not bulk_status,
                             use_container_width=True):
            try:
                updated = queries.bulk_set_status(bulk_status, **filters)
            except Exception as e:
                st.error(f"Nie udało się zmienić statusu: {e}")
            else:
                st.toast(f"Status zmieniony na '{status_label(bulk_status)}' dla {updated} leadów.")
                st.rerun()

    if st.button("Dodaj leada", use_container_width=True, key="btn_add_lead"):
        st.session_state["add_dialog_gen"] = st.session_state.get("add_dialog_gen", 0) + 1
        show_add_leads_dialog()

    # ── Lead table (current page only) ──
    render_lead_table_header(with_checkbox=True)
    for row in rows:
        if render_lead_row(row, with_checkbox=True):
            show_lead_dialog(row["id"])

    st.markdown("---")
    render_pagination(_PAGE_KEY, page_data["page"], page_data["pages"],
                      page_data["total"], "kontaktów")
