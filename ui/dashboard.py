import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import pandas as pd

from app.core.database import get_session_sync
from app.models.models import Lead, Company
from sqlalchemy.exc import IntegrityError
from datetime import datetime as dt
import uuid as uuid_lib

STATUS_OPTIONS = ["new", "sent", "opened", "replied", "bounced"]

STATUS_BADGES = {
    "new":     "🔵 new",
    "sent":    "📤 sent",
    "opened":  "👁️ opened",
    "replied": "💬 replied",
    "bounced": "❌ bounced",
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
        col3.metric("Status", STATUS_BADGES.get(lead.status, lead.status))

        if lead.company:
            col4, col5, col6 = st.columns(3)
            col4.metric("Lokalizacja", lead.company.location or "—")
            col5.metric("Branża", lead.company.industry or "—")
            col6.metric("Wielkość", lead.company.size_range or "—")

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
        if col_save.button("💾 Zapisz", type="primary", key=f"dialog_save_{lead_id}"):
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
                st.toast("✅ Zmiany zapisane!", icon="✅")
            else:
                st.toast("Brak zmian do zapisania.", icon="ℹ️")
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
    page_title="SALES BOT - PROIDEA", 
    page_icon="🤖", 
    layout="wide"
)

# 2. Nagłówek
st.title("🤖 SALES BOT - Centrum Dowodzenia")
st.markdown("Witaj w swoim prywatnym systemie zarządzania bazą kontaktów (PostgreSQL).")

# --- SIDEBAR FILTERS ---
with st.sidebar:
    st.header("🔍 Filtry")
    filter_email = st.text_input("Email", "")
    filter_name = st.text_input("Imię lub nazwisko", "")
    filter_company = st.text_input("Firma", "")
    filter_location = st.text_input("Lokalizacja (miasto/kraj)", "")
    filter_status = st.multiselect(
        "Status leada",
        options=["new", "sent", "opened", "replied", "bounced"],
        default=[],
        placeholder="Wszystkie statusy",
    )
    st.markdown("---")
    if st.button("Wyczyść filtry", use_container_width=True):
        st.rerun()

# 3. Podział na zakładki
tab_kontakty, tab_firmy, tab_import = st.tabs(["👥 Kontakty", "🏢 Baza Firm", "📥 Import"])

# --- ZAKŁADKA 1: KONTAKTY ---
with tab_kontakty:
    st.header("Twoje Kontakty")

    # Active filter badges
    active_filters = []
    if filter_email:
        active_filters.append(f"Email: *{filter_email}*")
    if filter_name:
        active_filters.append(f"Imię/Nazwisko: *{filter_name}*")
    if filter_company:
        active_filters.append(f"Firma: *{filter_company}*")
    if filter_location:
        active_filters.append(f"Lokalizacja: *{filter_location}*")
    if filter_status:
        active_filters.append(f"Status: *{', '.join(filter_status)}*")
    if active_filters:
        st.caption("Aktywne filtry: " + " | ".join(active_filters))

    try:
        from sqlalchemy.orm import joinedload

        session = next(get_session_sync())

        query = (
            session.query(Lead)
            .options(joinedload(Lead.company))
            .join(Company, Lead.company_id == Company.id, isouter=True)
        )

        if filter_email:
            query = query.filter(Lead.email.ilike(f"%{filter_email}%"))
        if filter_name:
            query = query.filter(
                (Lead.first_name.ilike(f"%{filter_name}%")) |
                (Lead.last_name.ilike(f"%{filter_name}%"))
            )
        if filter_company:
            query = query.filter(Company.name.ilike(f"%{filter_company}%"))
        if filter_location:
            query = query.filter(Company.location.ilike(f"%{filter_location}%"))
        if filter_status:
            query = query.filter(Lead.status.in_(filter_status))

        leads = query.order_by(Lead.created_at.desc()).all()

        # Collect all data before closing session
        leads_data = []
        for lead in leads:
            leads_data.append({
                "id": str(lead.id),
                "full_name": f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "—",
                "email": lead.email,
                "position": lead.position or "—",
                "company": lead.company.name if lead.company else "—",
                "status": lead.status,
                "notes": lead.notes or "",
                "created_at": lead.created_at.strftime("%Y-%m-%d"),
            })

        session.close()

        if not leads_data:
            st.info("Brak leadów w bazie danych. Zaimportuj dane w zakładce '📥 Import'.")
        else:
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Łącznie", len(leads_data))
            col2.metric("Nowe", sum(1 for l in leads_data if l["status"] == "new"))
            col3.metric("Firmy", len(set(l["company"] for l in leads_data if l["company"] != "—")))
            col4.metric("Ze stanowiskiem", sum(1 for l in leads_data if l["position"] != "—"))

            st.markdown("---")

            # Column headers
            h1, h2, h3, h4, h5, h6 = st.columns([3, 3, 2, 2, 1, 1])
            h1.markdown("**Imię i nazwisko**")
            h2.markdown("**Email**")
            h3.markdown("**Firma**")
            h4.markdown("**Stanowisko**")
            h5.markdown("**Status**")
            h6.markdown("")
            st.divider()

            for row in leads_data:
                c1, c2, c3, c4, c5, c6 = st.columns([3, 3, 2, 2, 1, 1])
                c1.markdown(row["full_name"])
                c2.markdown(f"`{row['email']}`")
                c3.markdown(row["company"])
                c4.markdown(row["position"])
                c5.markdown(STATUS_BADGES.get(row["status"], row["status"]))
                if c6.button("🔍", key=f"btn_{row['id']}", help="Otwórz profil kontaktu"):
                    show_lead_dialog(row["id"])

    except Exception as e:
        st.error(f"Błąd przy pobieraniu danych: {str(e)}")

# --- ZAKŁADKA 2: BAZA FIRM ---
with tab_firmy:
    st.header("Baza Firm (Account-Based View)")

    try:
        from sqlalchemy.orm import joinedload as jl

        firm_session = next(get_session_sync())

        firm_query = firm_session.query(Company).options(jl(Company.leads))
        if filter_company:
            firm_query = firm_query.filter(Company.name.ilike(f"%{filter_company}%"))
        if filter_location:
            firm_query = firm_query.filter(Company.location.ilike(f"%{filter_location}%"))
        companies = firm_query.order_by(Company.name).all()

        # Collect all data before closing session
        companies_data = []
        for company in companies:
            leads_list = []
            for lead in company.leads:
                leads_list.append({
                    "Imię": lead.first_name or "—",
                    "Nazwisko": lead.last_name or "—",
                    "Stanowisko": lead.position or "—",
                    "Email": lead.email,
                    "Status": lead.status,
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
                label = f"🏢 {co['name']} — {co['domain']}  ·  {lead_count} kontakt(ów)"
                with st.expander(label, expanded=False):
                    meta_col1, meta_col2, meta_col3 = st.columns(3)
                    meta_col1.markdown(f"**Branża:** {co['industry']}")
                    meta_col2.markdown(f"**Lokalizacja:** {co['location']}")
                    meta_col3.markdown(f"**Wielkość:** {co['size_range']}")

                    if co["leads"]:
                        st.markdown("**Kontakty w tej firmie:**")
                        df_leads = pd.DataFrame(co["leads"])
                        st.dataframe(
                            df_leads,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Status": st.column_config.TextColumn("Status", width="small"),
                                "Stanowisko": st.column_config.TextColumn("Stanowisko", width="medium"),
                            },
                        )
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
            st.error("⚠️ CSV musi zawierać kolumnę 'email' (lub podobnie nazwaną)")
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
                st.success(f"✅ Pomyślnie dodano {added_leads} lead(ów)")
            if skipped_leads > 0:
                st.warning(f"⚠️ Pominięto {skipped_leads} lead(ów) (duplikaty)")