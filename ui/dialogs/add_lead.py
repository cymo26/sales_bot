"""
"Dodaj Nowe Kontakty" dialog: up to 5 lead forms in one submit.

Each form block gets a UUID so widget keys survive add/remove of other blocks.
The opener must bump st.session_state["add_dialog_gen"] before calling the
dialog — that generation counter is what resets the form on a fresh open.
"""

import uuid as uuid_lib

import streamlit as st

from db import queries
from ui.constants import AVAILABLE_TAGS, STATUS_OPTIONS, status_label

_MAX_BLOCKS = 5
_FIELDS = ["fname", "lname", "email", "company", "position", "location",
           "linkedin", "status", "tags"]


def _clear_block_state(block_ids) -> None:
    for block_id in block_ids:
        for field in _FIELDS:
            st.session_state.pop(f"{field}_{block_id}", None)


@st.dialog("Dodaj Nowe Kontakty", width="large")
def show_add_leads_dialog():
    # Fresh open → wipe old blocks and start with one blank form
    gen = st.session_state.get("add_dialog_gen", 0)
    if st.session_state.get("_add_dlg_gen") != gen:
        _clear_block_state(st.session_state.get("lead_block_ids", []))
        st.session_state["lead_block_ids"] = [str(uuid_lib.uuid4())]
        st.session_state["_add_dlg_gen"] = gen

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
                # Fragment-scoped rerun redraws the dialog immediately with the
                # block gone, instead of leaving a stale form until next click.
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

        st.text_input("LinkedIn URL", key=f"linkedin_{block_id}", placeholder="https://linkedin.com/in/...")

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

        missing = [label for field, label in
                   [("fname", "Imię"), ("lname", "Nazwisko"),
                    ("email", "Email"), ("company", "Firma")]
                   if not values[field]]
        if missing:
            errors.append(f"Kontakt {pos}: brakuje — {', '.join(missing)}")
            continue

        leads_to_add.append({
            "first_name":   values["fname"],
            "last_name":    values["lname"],
            "email":        values["email"],
            "company_name": values["company"],
            "position":     values["position"] or None,
            "location":     values["location"] or None,
            "linkedin_url": values["linkedin"] or None,
            "status":       status,
            "tags":         ",".join(tags) if tags else None,
        })

    if errors:
        for err in errors:
            st.error(err)
        return

    # --- Persist (single transaction inside queries.create_leads) ---
    try:
        result = queries.create_leads(leads_to_add)
    except Exception as e:
        st.error(f"Nie udało się zapisać kontaktów: {e}")
        return

    _clear_block_state(block_ids)
    st.session_state.pop("lead_block_ids", None)
    st.session_state.pop("_add_dlg_gen", None)

    msg = f"Dodano {result['added']} kontakt(ów) do bazy!"
    if result["skipped"]:
        msg += f" Pominięto {len(result['skipped'])} duplikat(ów): {', '.join(result['skipped'])}"
    st.toast(msg)
    st.rerun()  # full-app rerun: closes the dialog and refreshes the tables
