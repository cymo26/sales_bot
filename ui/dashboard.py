import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unicodedata
import streamlit as st
import pandas as pd

from app.core.database import get_session_sync
from app.models.models import Lead, Company
from sqlalchemy.exc import IntegrityError
from datetime import datetime as dt
import uuid as uuid_lib
from html import escape as h

def _normalize(text: str) -> str:
    """Lowercase + strip diacritics so 'rys' matches 'ryś'."""
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii").lower()


STATUS_OPTIONS = ["nowy", "wysłany", "otwarty", "odpowiedział", "odbitka"]

STATUS_BADGES = {
    "nowy":         "nowy",
    "wysłany":      "wysłany",
    "otwarty":      "otwarty",
    "odpowiedział": "odpowiedział",
    "odbitka":      "odbitka",
}

STATUS_CLASS = {
    "nowy":         "lb-nowy",
    "wysłany":      "lb-sent",
    "otwarty":      "lb-opened",
    "odpowiedział": "lb-replied",
    "odbitka":      "lb-bounced",
}


@st.dialog("Profil Kontaktu", width="large")
def show_lead_dialog(lead_id: str):
    """Modal dialog showing full lead details with inline editing."""
    session = next(get_session_sync())
    try:
        from sqlalchemy.orm import joinedload as _jl
        lead = (
            session.query(Lead)
            .options(_jl(Lead.company))
            .filter(Lead.id == uuid_lib.UUID(lead_id))
            .first()
        )
        if lead is None:
            st.error("Nie znaleziono kontaktu.")
            return

        # --- Header ---
        full_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip() or lead.email
        company_name = lead.company.name if lead.company else "—"
        st.subheader(full_name)
        st.caption(f"{lead.position or '—'}  ·  {company_name}")
        st.markdown("---")

        # --- Details row ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Email", lead.email)
        col2.metric("Firma", company_name)
        col3.metric("Lokalizacja", lead.location or "—")

        col4, col5, col6 = st.columns(3)
        col4.metric("Status", STATUS_BADGES.get(lead.status, lead.status))
        col5.metric("Branza firmy", lead.company.industry or "—" if lead.company else "—")
        col6.metric("Wielkosc firmy", lead.company.size_range or "—" if lead.company else "—")

        st.markdown("---")

        # --- Editable section ---
        st.markdown("**Edytuj rekord**")
        new_status = st.selectbox(
            "Status",
            options=STATUS_OPTIONS,
            index=STATUS_OPTIONS.index(lead.status) if lead.status in STATUS_OPTIONS else 0,
            key=f"dialog_status_{lead_id}",
        )
        new_notes = st.text_area(
            "Notatki",
            value=lead.notes or "",
            height=120,
            max_chars=500,
            placeholder="Wpisz swoje notatki operacyjne…",
            key=f"dialog_notes_{lead_id}",
        )

        st.markdown("---")
        col_save, col_cancel = st.columns([1, 4])
        if col_save.button("Zapisz zmiany", type="primary", key=f"dialog_save_{lead_id}"):
            changed = False
            if lead.status != new_status:
                lead.status = new_status
                changed = True
            resolved_notes = new_notes.strip() if new_notes.strip() else None
            if lead.notes != resolved_notes:
                lead.notes = resolved_notes
                changed = True
            if changed:
                lead.updated_at = dt.utcnow()
                session.commit()
                st.toast("Zmiany zapisane!")
            else:
                st.toast("Brak zmian do zapisania.")
            st.rerun()

    except Exception as e:
        st.error(f"Błąd: {str(e)}")
    finally:
        session.close()


def detect_column_mapping(df_columns):
    """
    Intelligently map CSV columns to Lead model fields.
    Handles variations in column names (capitalization, spaces, underscores, etc.)
    """
    # Normalize columns: lowercase, replace spaces with underscores
    normalized_columns = {col.lower().replace(' ', '_'): col for col in df_columns}
    
    # Define patterns to match for each field
    patterns = {
        'email': [
            'work_email',
            'work_e_mail',
            'email',
            'e_mail',
            'e-mail',
            'mail',
            'emailaddress',
            'email_address',
        ],
        'first_name': [
            'first_name',
            'firstname',
            'first',
            'name_first',
            'imie',
            'given_name',
            'forename',
        ],
        'last_name': [
            'last_name',
            'lastname',
            'last',
            'surname',
            'name_last',
            'nazwisko',
            'family_name',
        ],
        'position': [
            'job_title',
            'jobtitle',
            'job',
            'title',
            'role',
            'stanowisko',
            'headline',
            'position',
        ],
        'company': [
            'company_name',
            'companyname',
            'company',
            'firma',
            'organisation',
            'organization',
            'employer',
            'organization_name',
        ],
        'location': [
            'city',
            'miasto',
            'lokalizacja',
            'location',
            'loc',
            'region',
            'kraj',
            'country',
            'address',
        ],
        'linkedin_url': [
            'linkedin_url',
            'linkedin',
            'linkedin_profile',
            'profile_url',
            'profile',
            'li_url',
            'li_profile',
            'social',
            'link',
        ],
    }

    mapping = {}
    
    # Try to match each field
    for field, field_patterns in patterns.items():
        for pattern in field_patterns:
            if pattern in normalized_columns:
                mapping[field] = normalized_columns[pattern]
                break
    
    return mapping


# 1. Konfiguracja strony (musi być pierwszą komendą Streamlit)
st.set_page_config(
    page_title="ZIPEK BOT",
    layout="wide"
)

# 2. Nagłówek
st.title("ZIPEK BOT")

# --- LOAD DISTINCT FILTER VALUES ---
try:
    _meta_session = next(get_session_sync())
    _distinct_locs = [
        r[0] for r in _meta_session.query(Lead.location)
        .filter(Lead.location.isnot(None))
        .distinct()
        .order_by(Lead.location)
        .all()
    ]
    _distinct_positions = [
        r[0] for r in _meta_session.query(Lead.position)
        .filter(Lead.position.isnot(None))
        .distinct()
        .order_by(Lead.position)
        .all()
    ]
    _meta_session.close()
except Exception:
    _distinct_locs = []
    _distinct_positions = []

with st.sidebar:
    st.header("Filtry")
    st.markdown("---")
    if st.button("Wyczyść filtry", use_container_width=True):
        for _k in ["f_search_k", "f_search_f", "f_location_k", "f_status_k", "f_position_k", "f_location_f"]:
            st.session_state.pop(_k, None)
        st.rerun()

# 3. Podział na zakładki
# Detect ?lead_id= from HTML row click BEFORE tabs are rendered.
# Storing in session_state survives the rerun caused by clearing query_params.
if 'lead_id' in st.query_params:
    st.session_state['_open_lead'] = st.query_params['lead_id']
    del st.query_params['lead_id']   # triggers one more rerun; dialog opens on that rerun
    st.stop()                        # halt current rerun here — next rerun will show dialog
# Badge styles + row hover effect
st.markdown("""
<style>
/* ═══════════════════════════════════════════════════════
   ZIPEK BOT — Premium Dark Theme
═══════════════════════════════════════════════════════ */

/* ── Global layout ── */
section.main > div { padding-top: 1rem; }
h1 { letter-spacing: -0.025em !important; }
h2 { letter-spacing: -0.015em !important; }

/* ── Status badges ── */
.lbadge {
    display: inline-flex;
    align-items: center;
    padding: 2px 10px;
    border-radius: 99px;
    font-size: 0.69rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    white-space: nowrap;
}
.lb-nowy    { background: rgba(59,130,246,.13);  color: #60a5fa; border: 1px solid rgba(59,130,246,.30); }
.lb-sent    { background: rgba(139,92,246,.13);  color: #a78bfa; border: 1px solid rgba(139,92,246,.30); }
.lb-opened  { background: rgba(16,185,129,.13);  color: #34d399; border: 1px solid rgba(16,185,129,.30); }
.lb-replied { background: rgba(245,158,11,.13);  color: #fbbf24; border: 1px solid rgba(245,158,11,.30); }
.lb-bounced { background: rgba(239,68,68,.13);   color: #f87171; border: 1px solid rgba(239,68,68,.30); }

/* ── Row hover ── */
div[data-testid="stHorizontalBlock"]:has(.row-hover-marker) {
    padding: 5px 10px;
    border-radius: 8px;
    transition: background-color .15s ease;
    align-items: center;
}
div[data-testid="stHorizontalBlock"]:has(.row-hover-marker):hover {
    background-color: rgba(255,255,255,.04);
}
div[data-testid="stHorizontalBlock"]:has(.row-hover-marker) p {
    margin-bottom: 0;
    line-height: 1.35;
}
.row-hover-marker { display: none; }

/* ── Row action button (Szczegóły) ── */
div[data-testid="stHorizontalBlock"]:has(.row-hover-marker) div[data-testid="stButton"] button {
    padding: 2px 10px !important;
    height: 26px !important;
    font-size: 0.72rem !important;
    border-radius: 6px !important;
    border: 1px solid rgba(255,255,255,.1) !important;
    background: rgba(255,255,255,.04) !important;
    color: rgba(255,255,255,.55) !important;
    transition: all .15s ease;
}
div[data-testid="stHorizontalBlock"]:has(.row-hover-marker) div[data-testid="stButton"] button:hover {
    background: rgba(255,255,255,.09) !important;
    color: rgba(255,255,255,.9) !important;
    border-color: rgba(255,255,255,.22) !important;
}

/* ── LinkedIn link button ── */
div[data-testid="stHorizontalBlock"]:has(.row-hover-marker) a[data-testid="stLinkButton"],
div[data-testid="stHorizontalBlock"]:has(.row-hover-marker) [data-testid="stLinkButton"] a {
    padding: 2px 6px !important;
    height: 26px !important;
    font-size: 0.78rem !important;
    border-radius: 6px !important;
    border: 1px solid rgba(99,102,241,.3) !important;
    background: rgba(99,102,241,.07) !important;
    color: #818cf8 !important;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    transition: all .15s ease;
}
div[data-testid="stHorizontalBlock"]:has(.row-hover-marker) a[data-testid="stLinkButton"]:hover,
div[data-testid="stHorizontalBlock"]:has(.row-hover-marker) [data-testid="stLinkButton"] a:hover {
    background: rgba(99,102,241,.16) !important;
    color: #a5b4fc !important;
    border-color: rgba(99,102,241,.5) !important;
}

/* ── Metric cards ── */
div[data-testid="stMetric"] {
    background: rgba(255,255,255,.03);
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 10px;
    padding: 10px 14px !important;
}
div[data-testid="stMetricValue"] {
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}
div[data-testid="stMetricLabel"] p {
    font-size: 0.68rem !important;
    letter-spacing: 0.07em !important;
    text-transform: uppercase;
    opacity: .45;
    margin-bottom: 2px !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] > div { padding-top: 1.5rem; }
section[data-testid="stSidebar"] { border-right: 1px solid rgba(255,255,255,.06); }

/* ── Dividers ── */
hr { border-color: rgba(255,255,255,.07) !important; margin: 4px 0 8px !important; }

/* ── Filter bar inputs — subtle fill ── */
div[data-testid="stTextInput"] input {
    background: rgba(255,255,255,.04) !important;
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)

tab_kontakty, tab_firmy, tab_import = st.tabs(["👥 Kontakty", "🏢 Baza Firm", "📥 Import"])

# Open dialog if session_state was set by the param handler above
if '_open_lead' in st.session_state:
    show_lead_dialog(st.session_state.pop('_open_lead'))

# --- ZAKŁADKA 1: KONTAKTY ---
with tab_kontakty:

    # Header row: title left, delete button right
    col_title, col_del_btn = st.columns([5, 1])
    col_title.header("Twoje Kontakty")

    # Read filter values from previous render (session_state trick: widgets placed after query)
    _search_k = st.session_state.get("f_search_k", "")
    _filter_location_k = st.session_state.get("f_location_k", [])
    _filter_status_k = st.session_state.get("f_status_k", [])
    _filter_position_k = st.session_state.get("f_position_k", [])

    try:
        from sqlalchemy.orm import joinedload

        session = next(get_session_sync())

        # Fetch ALL leads — exact filters applied client-side for cascading behaviour
        query = (
            session.query(Lead)
            .options(joinedload(Lead.company))
            .join(Company, Lead.company_id == Company.id, isouter=True)
        )
        leads = query.order_by(Lead.created_at.desc()).all()

        all_leads_data = []
        for lead in leads:
            all_leads_data.append({
                "id": str(lead.id),
                "first_name": lead.first_name or "",
                "last_name": lead.last_name or "",
                "full_name": f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "—",
                "email": lead.email,
                "position": lead.position or "—",
                "company": lead.company.name if lead.company else "—",
                "location": lead.location or "—",
                "linkedin_url": lead.linkedin_url or "",
                "status": lead.status,
                "notes": lead.notes or "",
                "created_at": lead.created_at.strftime("%Y-%m-%d"),
            })

        session.close()

        # 1. Text search (accent-insensitive, name + email + company)
        if _search_k:
            _q = _normalize(_search_k)
            _text_filtered = [
                row for row in all_leads_data
                if _q in _normalize(row["full_name"])
                or _q in _normalize(row["email"])
                or _q in _normalize(row["company"])
            ]
        else:
            _text_filtered = all_leads_data

        # 2. Cascading filter options — each list excludes its own filter so options stay visible
        def _apply_exact(data, loc=(), pos=(), stat=()):
            r = data
            if loc: r = [x for x in r if x["location"] in loc]
            if pos: r = [x for x in r if x["position"] in pos]
            if stat: r = [x for x in r if x["status"] in stat]
            return r

        _avail_locs = sorted({r["location"] for r in _apply_exact(_text_filtered, pos=_filter_position_k, stat=_filter_status_k) if r["location"] != "—"})
        _avail_pos  = sorted({r["position"]  for r in _apply_exact(_text_filtered, loc=_filter_location_k, stat=_filter_status_k) if r["position"] != "—"})
        _avail_stat = sorted({r["status"]    for r in _apply_exact(_text_filtered, loc=_filter_location_k, pos=_filter_position_k)})

        # 3. Drop any selected values that no longer exist in available options
        for _fk, _av in [("f_location_k", _avail_locs), ("f_position_k", _avail_pos), ("f_status_k", _avail_stat)]:
            if _fk in st.session_state:
                st.session_state[_fk] = [v for v in st.session_state[_fk] if v in _av]
        _filter_location_k = st.session_state.get("f_location_k", [])
        _filter_position_k = st.session_state.get("f_position_k", [])
        _filter_status_k   = st.session_state.get("f_status_k", [])

        # 4. Final dataset
        leads_data = _apply_exact(_text_filtered, loc=_filter_location_k, pos=_filter_position_k, stat=_filter_status_k)

        # Active filter badges (shown after computation so values are always accurate)
        active_filters = []
        if _search_k:
            active_filters.append(f"Szukaj: *{_search_k}*")
        if _filter_location_k:
            active_filters.append(f"Lokalizacja: *{', '.join(_filter_location_k)}*")
        if _filter_status_k:
            active_filters.append(f"Status: *{', '.join(_filter_status_k)}*")
        if _filter_position_k:
            active_filters.append(f"Stanowisko: *{', '.join(_filter_position_k)}*")
        if active_filters:
            st.caption("Aktywne filtry: " + " | ".join(active_filters))

        # Delete button — always render into header column so layout is stable
        pending_deletes = [
            row["id"] for row in leads_data
            if st.session_state.get(f"del_{row['id']}", False)
        ]
        btn_label = f"Usuń zaznaczone ({len(pending_deletes)})" if pending_deletes else "Usuń zaznaczone"
        if col_del_btn.button(btn_label, type="primary", disabled=not pending_deletes, key="bulk_delete_btn"):
            del_session = next(get_session_sync())
            try:
                for lid in pending_deletes:
                    lead_obj = del_session.query(Lead).filter(Lead.id == uuid_lib.UUID(lid)).first()
                    if lead_obj:
                        del_session.delete(lead_obj)
                del_session.commit()
                for lid in pending_deletes:
                    st.session_state.pop(f"del_{lid}", None)
                st.toast(f"Usunięto {len(pending_deletes)} kontakt(ów).")
            finally:
                del_session.close()
            st.rerun()

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Lacznie", len(leads_data))
        col2.metric("Nowe", sum(1 for l in leads_data if l["status"] == "new"))
        col3.metric("Firmy", len(set(l["company"] for l in leads_data if l["company"] != "—")))
        col4.metric("Ze stanowiskiem", sum(1 for l in leads_data if l["position"] != "—"))

        # Filter bar — always visible so user can clear filters even when results are empty
        col_search, col_loc, col_pos, col_status, col_export = st.columns([2.5, 1.5, 2, 1.5, 1])
        col_search.text_input(
            "Szukaj",
            placeholder="Imię nazwisko, email, firma...",
            key="f_search_k",
            label_visibility="collapsed",
        )
        col_loc.multiselect(
            "Lokalizacja",
            options=_avail_locs,
            default=[],
            placeholder="Lokalizacja",
            key="f_location_k",
            label_visibility="collapsed",
        )
        col_pos.multiselect(
            "Stanowisko",
            options=_avail_pos,
            default=[],
            placeholder="Stanowisko",
            key="f_position_k",
            label_visibility="collapsed",
        )
        col_status.multiselect(
            "Status",
            options=_avail_stat,
            default=[],
            placeholder="Status",
            key="f_status_k",
            label_visibility="collapsed",
        )

        export_df = pd.DataFrame([
            {
                "Email": r["email"],
                "First Name": r["first_name"],
                "Last Name": r["last_name"],
                "Company": r["company"],
                "Position": r["position"],
                "Location": r["location"],
                "Status": r["status"],
            }
            for r in leads_data
        ])
        col_export.download_button(
            label=f"Eksportuj CSV ({len(leads_data)})",
            data=export_df.to_csv(index=False).encode("utf-8"),
            file_name="apple_script_outreach.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not leads_data,
        )

        if not leads_data:
            any_filter = _search_k or _filter_location_k or _filter_status_k or _filter_position_k
            if any_filter:
                st.info("Brak wyników dla aktualnych filtrów. Zmień kryteria lub wyczyść filtry.")
            else:
                st.info("Brak leadów w bazie danych. Zaimportuj dane w zakładce 'Import'.")
        else:
            st.markdown("---")

            # Column header row
            h0, h1, h2, h3, h4, h5, h6, h_li, h7 = st.columns([0.4, 2, 2.5, 2, 2.5, 1.5, 1, 0.8, 1])
            for col, label in zip(
                [h0, h1, h2, h3, h4, h5, h6, h_li, h7],
                ["", "Imie i Nazwisko", "Email", "Firma", "Stanowisko", "Lokalizacja", "Status", "LN", ""],
            ):
                col.markdown(
                    f"<small style='font-weight:700;text-transform:uppercase;"
                    f"letter-spacing:.06em;opacity:.45'>{label}</small>",
                    unsafe_allow_html=True,
                )
            st.divider()

            # Lead rows
            for row in leads_data:
                c0, c1, c2, c3, c4, c5, c6, c_li, c_act = st.columns([0.4, 2, 2.5, 2, 2.5, 1.5, 1, 0.8, 1])
                c0.checkbox("", key=f"del_{row['id']}", label_visibility="collapsed")
                c1.markdown(f"<span class='row-hover-marker'></span>**{h(row['full_name'])}**", unsafe_allow_html=True)
                c2.markdown(
                    f"<span style='font-size:.88rem;font-family:ui-monospace,monospace;"
                    f"color:#a3a8b8'>{h(row['email'])}</span>",
                    unsafe_allow_html=True,
                )
                c3.write(row['company'])
                c4.write(row['position'])
                c5.write(row['location'])
                c6.markdown(
                    f"<span class='lbadge {STATUS_CLASS.get(row['status'], 'lb-nowy')}'>{h(row['status'])}</span>",
                    unsafe_allow_html=True,
                )
                if row['linkedin_url']:
                    c_li.link_button("🔗", row['linkedin_url'], use_container_width=True)
                else:
                    c_li.markdown("<span style='opacity:.2;font-size:.8rem'>—</span>", unsafe_allow_html=True)
                if c_act.button("Szczegóły", key=f"btn_{row['id']}"):
                    show_lead_dialog(row['id'])

    except Exception as e:
        st.error(f"Blad przy pobieraniu danych: {str(e)}")

# --- ZAKŁADKA 2: BAZA FIRM ---
with tab_firmy:
    st.header("Baza Firm (Account-Based View)")
    col_fsearch, col_floc = st.columns([3, 2])
    filter_search_f = col_fsearch.text_input(
        "Szukaj po nazwie firmy",
        placeholder="np. Acme, Comarch...",
        key="f_search_f",
        label_visibility="collapsed",
    )
    filter_location_f = col_floc.multiselect(
        "Lokalizacja",
        options=_distinct_locs,
        default=[],
        placeholder="Lokalizacja",
        key="f_location_f",
        label_visibility="collapsed",
    )

    try:
        from sqlalchemy.orm import joinedload as jl

        firm_session = next(get_session_sync())

        firm_query = firm_session.query(Company).options(jl(Company.leads))
        if filter_search_f:
            firm_query = firm_query.filter(Company.name.ilike(f"%{filter_search_f}%"))
        if filter_location_f:
            firm_query = firm_query.filter(Company.location.in_(filter_location_f))
        companies = firm_query.order_by(Company.name).all()

        # Collect all data before closing session
        companies_data = []
        for company in companies:
            leads_list = []
            for lead in company.leads:
                leads_list.append({
                    "id": str(lead.id),
                    "full_name": f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "—",
                    "email": lead.email,
                    "company": company.name,
                    "position": lead.position or "—",
                    "location": lead.location or "—",
                    "linkedin_url": lead.linkedin_url or "",
                    "status": lead.status,
                })
            companies_data.append({
                "name": company.name,
                "domain": company.domain,
                "industry": company.industry or "—",
                "location": company.location or "—",
                "size_range": company.size_range or "—",
                "leads": leads_list,
            })

        firm_session.close()

        if not companies_data:
            st.info("Brak firm w bazie danych.")
        else:
            st.caption(f"Znaleziono **{len(companies_data)}** firm(y).")
            for co in companies_data:
                lead_count = len(co["leads"])
                label = f"{co['name']} — {co['domain']}  ·  {lead_count} kontakt(ow)"
                with st.expander(label, expanded=False):
                    meta_col1, meta_col2, meta_col3 = st.columns(3)
                    meta_col1.markdown(f"**Branża:** {co['industry']}")
                    meta_col2.markdown(f"**Lokalizacja:** {co['location']}")
                    meta_col3.markdown(f"**Wielkość:** {co['size_range']}")

                    if co["leads"]:
                        st.markdown("**Kontakty w tej firmie:**")

                        # Header row
                        fh1, fh2, fh3, fh4, fh5, fh6, fh_li, fh7 = st.columns([2, 2.5, 2, 2.5, 1.5, 1, 0.8, 1])
                        for col, label_h in zip(
                            [fh1, fh2, fh3, fh4, fh5, fh6, fh_li, fh7],
                            ["Imie i Nazwisko", "Email", "Firma", "Stanowisko", "Lokalizacja", "Status", "LN", ""],
                        ):
                            col.markdown(
                                f"<small style='font-weight:700;text-transform:uppercase;"
                                f"letter-spacing:.06em;opacity:.45'>{label_h}</small>",
                                unsafe_allow_html=True,
                            )
                        st.divider()

                        for row in co["leads"]:
                            c1, c2, c3, c4, c5, c6, c_li, c_act = st.columns([2, 2.5, 2, 2.5, 1.5, 1, 0.8, 1])
                            c1.markdown(f"<span class='row-hover-marker'></span>**{h(row['full_name'])}**", unsafe_allow_html=True)
                            c2.markdown(
                                f"<span style='font-size:.88rem;font-family:ui-monospace,monospace;"
                                f"color:#a3a8b8'>{h(row['email'])}</span>",
                                unsafe_allow_html=True,
                            )
                            c3.write(row['company'])
                            c4.write(row['position'])
                            c5.write(row['location'])
                            c6.markdown(
                                f"<span class='lbadge {STATUS_CLASS.get(row['status'], 'lb-nowy')}'>{h(row['status'])}</span>",
                                unsafe_allow_html=True,
                            )
                            if row['linkedin_url']:
                                c_li.link_button("🔗", row['linkedin_url'], use_container_width=True)
                            else:
                                c_li.markdown("<span style='opacity:.2;font-size:.8rem'>—</span>", unsafe_allow_html=True)
                            if c_act.button("Szczegóły", key=f"btn_co_{row['id']}"):
                                show_lead_dialog(row['id'])
                    else:
                        st.caption("Brak przypisanych kontaktów.")

    except Exception as e:
        st.error(f"Błąd przy pobieraniu firm: {str(e)}")


# --- ZAKŁADKA 3: IMPORT PLIKÓW ---
with tab_import:
    st.header("Importuj nowe kontakty")
    st.markdown("Wgraj plik CSV (np. z Eventory lub Livespace), aby dodać rekordy do bazy.")
    
    uploaded_file = st.file_uploader("Przeciągnij i upuść plik CSV tutaj", type=["csv"])
    
    if uploaded_file is not None:
        # Odczyt pliku do pandas DataFrame (tylko do podglądu)
        df = pd.read_csv(uploaded_file)
        
        st.success(f"Pomyślnie wczytano plik: {uploaded_file.name}")
        st.markdown(f"**Podgląd pierwszych 5 wierszy z {len(df)}**")
        st.dataframe(df.head())
        
    # Przycisk, który docelowo uruchomi Pydantic i zapis do PostgreSQL
    if st.button("Zapisz do bazy PostgreSQL", type="primary"):
        if df is None or df.empty:
            st.error("Proszę najpierw wczytać plik CSV")
        else:
            # Auto-detect column mapping
            column_mapping = detect_column_mapping(df.columns)
        
        if not column_mapping or 'email' not in column_mapping:
            st.error("CSV musi zawierac kolumne 'email' (lub podobnie nazwana)")
        else:
            st.info(f"Wykryto kolumny: {column_mapping}")
            
            added_leads = 0
            skipped_leads = 0
            session = next(get_session_sync())
            
            try:
                for index, row in df.iterrows():
                    try:
                        lead_data = {}
                        company_id = None
                        
                        # Process standard fields
                        for field, csv_col in column_mapping.items():
                            if field == 'company':
                                # Handle company separately
                                continue
                            
                            value = row[csv_col]
                            # Skip empty strings and "❌" error messages
                            if pd.notna(value) and not str(value).startswith('❌'):
                                lead_data[field] = str(value).strip()
                        
                        # Handle company field - create or find company
                        if 'company' in column_mapping:
                            company_name = row[column_mapping['company']]
                            if pd.notna(company_name) and not str(company_name).startswith('❌'):
                                company_name = str(company_name).strip()
                                
                                # Check if company already exists
                                existing_company = session.query(Company).filter(
                                    Company.name == company_name
                                ).first()
                                
                                if existing_company:
                                    company_id = existing_company.id
                                else:
                                    # Create new company
                                    # Generate domain from company name (lowercase, replace spaces with -)
                                    domain = company_name.lower().replace(' ', '-')[:50]
                                    
                                    new_company = Company(
                                        name=company_name,
                                        domain=domain
                                    )
                                    session.add(new_company)
                                    session.flush()  # Flush to get the ID
                                    company_id = new_company.id
                        
                        # Add company_id to lead data if found
                        if company_id:
                            lead_data['company_id'] = company_id
                        
                        if 'email' in lead_data:  # Email is required
                            new_lead = Lead(**lead_data)
                            session.add(new_lead)
                            session.commit()
                            added_leads += 1
                        
                    except IntegrityError as e:
                        session.rollback()
                        if 'company' in str(e).lower() and 'domain' in str(e).lower():
                            st.warning(f"Wiersz {index + 1}: Firma z taką domeną już istnieje")
                        else:
                            skipped_leads += 1
                    except Exception as e:
                        session.rollback()
                        st.warning(f"Błąd w wierszu {index + 1}: {str(e)}")
                        skipped_leads += 1
            
            finally:
                session.close()
                st.success("Import zakończony! Zobacz wyniki poniżej.")
    
            
            # Display results
            if added_leads > 0:
                st.success(f"Pomyslnie dodano {added_leads} lead(ow)")
            if skipped_leads > 0:
                st.warning(f"Pominieto {skipped_leads} lead(ow) (duplikaty)")