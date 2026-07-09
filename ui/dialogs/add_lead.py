"""
"Dodaj Nowe Kontakty" dialog: up to 5 lead forms in one submit.

Each form block gets a UUID so widget keys survive add/remove of other blocks.
The opener must bump st.session_state["add_dialog_gen"] before calling the
dialog — that generation counter is what resets the form on a fresh open.

Industry ("Smart Select"): options = defaults ∪ industries already in the DB
(db.queries.fetch_industries), plus a trailing "+ Dodaj nową branżę..." entry
that reveals a free-text input. Submitting runs a DRY RUN
(preview_industry_conflicts): if an existing company already has a different
industry, the dialog switches to a conflict-resolution view (keep vs.
overwrite, per company) before anything is committed.
"""

import uuid as uuid_lib

import streamlit as st

from db import queries
from ui.constants import (ADD_NEW_INDUSTRY, AVAILABLE_TAGS, STATUS_OPTIONS,
                          status_label)

_MAX_BLOCKS = 5
_FIELDS = ["fname", "lname", "email", "company", "position", "location",
           "linkedin", "status", "tags", "industry", "industry_new"]


def _clear_block_state(block_ids) -> None:
    for block_id in block_ids:
        for field in _FIELDS:
            st.session_state.pop(f"{field}_{block_id}", None)


def _clear_dialog_state() -> None:
    _clear_block_state(st.session_state.get("lead_block_ids", []))
    for conflict in st.session_state.get("_industry_conflicts", []):
        st.session_state.pop(f"conflict_{conflict['company']}", None)
    for key in ["lead_block_ids", "_add_dlg_gen", "_pending_leads", "_industry_conflicts"]:
        st.session_state.pop(key, None)


def _persist(leads: list) -> None:
    """Commit resolved leads, clean the dialog up, close it. st.rerun() stays
    outside the try so it can't be swallowed."""
    try:
        result = queries.create_leads(leads)
    except Exception as e:
        st.error(f"Nie udało się zapisać kontaktów: {e}")
        return
    _clear_dialog_state()
    msg = f"Dodano {result['added']} kontakt(ów) do bazy!"
    if result["skipped"]:
        msg += f" Pominięto {len(result['skipped'])} duplikat(ów): {', '.join(result['skipped'])}"
    st.toast(msg)
    st.rerun()  # full-app rerun: closes the dialog and refreshes the tables


def _render_conflict_resolution() -> None:
    """Dry-run found existing companies with a different industry — let the
    user decide per company before anything is written."""
    conflicts = st.session_state["_industry_conflicts"]
    st.markdown("**Wykryto konflikt branży**")
    st.caption(
        "Te firmy już istnieją w bazie z inną branżą. Zdecyduj dla każdej, "
        "czy zachować obecną wartość, czy nadpisać nową — nic nie zostało "
        "jeszcze zapisane."
    )
    for conflict in conflicts:
        st.radio(
            f"**{conflict['company']}**",
            options=["keep", "overwrite"],
            format_func=lambda opt, c=conflict: (
                f"Zachowaj obecną: „{c['current']}”" if opt == "keep"
                else f"Nadpisz na: „{c['incoming']}”"
            ),
            key=f"conflict_{conflict['company']}",
            horizontal=True,
        )

    st.markdown("---")
    col_ok, col_back = st.columns(2)
    if col_ok.button("Zatwierdź i zapisz", type="primary", use_container_width=True,
                     key="conflict_confirm"):
        decisions = {
            c["company"]: st.session_state.get(f"conflict_{c['company']}", "keep")
            for c in conflicts
        }
        leads = [dict(ld) for ld in st.session_state["_pending_leads"]]
        for ld in leads:
            if decisions.get(ld.get("company_name")) == "keep":
                ld["company_industry"] = None
        _persist(leads)
    if col_back.button("Wróć do formularza", use_container_width=True,
                       key="conflict_back"):
        for conflict in conflicts:
            st.session_state.pop(f"conflict_{conflict['company']}", None)
        st.session_state.pop("_pending_leads", None)
        st.session_state.pop("_industry_conflicts", None)
        st.rerun(scope="fragment")


@st.dialog("Dodaj Nowe Kontakty", width="large")
def show_add_leads_dialog():
    # Fresh open → wipe everything (form blocks AND any stale conflict state)
    gen = st.session_state.get("add_dialog_gen", 0)
    if st.session_state.get("_add_dlg_gen") != gen:
        _clear_dialog_state()
        st.session_state["lead_block_ids"] = [str(uuid_lib.uuid4())]
        st.session_state["_add_dlg_gen"] = gen

    # Mid-submit with unresolved industry conflicts → resolution view instead
    if "_pending_leads" in st.session_state:
        _render_conflict_resolution()
        return

    try:
        industries = queries.fetch_industries()
    except Exception:
        industries = list(queries.DEFAULT_INDUSTRIES)
    industry_options = [""] + industries + [ADD_NEW_INDUSTRY]

    block_ids = st.session_state["lead_block_ids"]
    count = len(block_ids)

    for idx, block_id in enumerate(block_ids, 1):
        if count > 1:
            hcol, xcol = st.columns([11, 1])
            hcol.markdown(
                f"<small style='font-weight:700;text-transform:uppercase;"
                f"letter-spacing:.06em;opacity:.45'>Kontakt {idx}</small>",
                unsafe_allow_html=True,
            )
            if xcol.button("🗑️", key=f"del_{block_id}", help="Usuń formularz"):
                block_ids.remove(block_id)
                _clear_block_state([block_id])
                st.rerun(scope="fragment")

        r1a, r1b = st.columns(2)
        r1a.text_input("Imię *",      key=f"fname_{block_id}",    placeholder="Jan")
        r1b.text_input("Nazwisko *",  key=f"lname_{block_id}",    placeholder="Kowalski")

        r2a, r2b = st.columns(2)
        r2a.text_input("Email *",     key=f"email_{block_id}",    placeholder="jan@firma.pl")
        r2b.text_input("Firma *",     key=f"company_{block_id}",  placeholder="Acme Sp. z o.o.")

        r3a, r3b = st.columns(2)
        r3a.text_input("Stanowisko",  key=f"position_{block_id}", placeholder="CISO")
        r3b.text_input("Lokalizacja", key=f"location_{block_id}", placeholder="Warszawa")

        r4a, r4b = st.columns(2)
        r4a.text_input("LinkedIn URL", key=f"linkedin_{block_id}",
                       placeholder="https://linkedin.com/in/...")
        r4b.selectbox(
            "Branża firmy",
            options=industry_options,
            format_func=lambda opt: "— wybierz (opcjonalne) —" if opt == "" else opt,
            key=f"industry_{block_id}",
        )
        if st.session_state.get(f"industry_{block_id}") == ADD_NEW_INDUSTRY:
            r4b.text_input("Wpisz nazwę nowej branży",
                           key=f"industry_new_{block_id}",
                           placeholder="np. GreenTech / Energy")

        r5a, r5b = st.columns(2)
        r5a.selectbox("Status", options=STATUS_OPTIONS, format_func=status_label,
                      key=f"status_{block_id}")
        r5b.multiselect("Tagi", options=AVAILABLE_TAGS, key=f"tags_{block_id}")

        if block_id != block_ids[-1]:
            st.markdown("---")

    st.markdown("---")
    col_add, col_spacer = st.columns([2, 5])
    if col_add.button("Dodaj kolejną osobę", disabled=count >= _MAX_BLOCKS,
                      use_container_width=True, key="add_block_btn"):
        block_ids.append(str(uuid_lib.uuid4()))
        st.rerun(scope="fragment")
    if count >= _MAX_BLOCKS:
        col_spacer.caption(f"Osiągnięto limit {_MAX_BLOCKS} kontaktów.")

    label_map = {1: "osobę", 2: "osoby", 3: "osoby", 4: "osoby", 5: "osób"}
    if not st.button(
        f"Dodaj {count} {label_map.get(count, 'osób')} do bazy kontaktów",
        type="primary", use_container_width=True, key="mf_submit",
    ):
        return

    # --- Validation ---
    errors, leads_to_add = [], []
    for pos, block_id in enumerate(block_ids, 1):
        values = {f: (st.session_state.get(f"{f}_{block_id}") or "") for f in _FIELDS[:7]}
        values = {f: v.strip() for f, v in values.items()}
        status = st.session_state.get(f"status_{block_id}", STATUS_OPTIONS[0])
        tags = st.session_state.get(f"tags_{block_id}", [])

        industry = st.session_state.get(f"industry_{block_id}", "")
        if industry == ADD_NEW_INDUSTRY:
            industry = (st.session_state.get(f"industry_new_{block_id}") or "").strip()
            if not industry:
                errors.append(f"Kontakt {pos}: wpisz nazwę nowej branży lub wybierz istniejącą.")

        missing = [label for field, label in
                   [("fname", "Imię"), ("lname", "Nazwisko"),
                    ("email", "Email"), ("company", "Firma")]
                   if not values[field]]
        if missing:
            errors.append(f"Kontakt {pos}: brakuje — {', '.join(missing)}")
            continue

        leads_to_add.append({
            "first_name":       values["fname"],
            "last_name":        values["lname"],
            "email":            values["email"],
            "company_name":     values["company"],
            "company_industry": industry or None,
            "position":         values["position"] or None,
            "location":         values["location"] or None,
            "linkedin_url":     values["linkedin"] or None,
            "status":           status,
            "tags":             ",".join(tags) if tags else None,
        })

    if errors:
        for err in errors:
            st.error(err)
        return

    # --- DRY RUN: industry conflicts on existing companies? ---
    company_industries = {}
    for ld in leads_to_add:
        if ld["company_industry"]:
            company_industries.setdefault(ld["company_name"], ld["company_industry"])
    try:
        conflicts = queries.preview_industry_conflicts(company_industries)
    except Exception as e:
        st.error(f"Nie udało się sprawdzić konfliktów: {e}")
        return

    if conflicts:
        st.session_state["_pending_leads"] = leads_to_add
        st.session_state["_industry_conflicts"] = conflicts
        st.rerun(scope="fragment")

    _persist(leads_to_add)
