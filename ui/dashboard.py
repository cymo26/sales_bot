import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import pandas as pd

from app.core.database import get_session_sync
from app.models.models import Lead, Company
from sqlalchemy.exc import IntegrityError

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
tab_baza, tab_import = st.tabs(["📊 Baza Główna (Master)", "📥 Import Danych (CSV)"])

# --- ZAKŁADKA 1: GŁÓWNA BAZA ---
with tab_baza:
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

    # Fetch leads from database
    try:
        from sqlalchemy.orm import joinedload
        
        session = next(get_session_sync())
        
        # Build query with eager loading of company
        query = session.query(Lead).options(joinedload(Lead.company)).join(Company, Lead.company_id == Company.id, isouter=True)
        
        # Apply sidebar filters
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
        
        # Get all leads
        leads = query.order_by(Lead.created_at.desc()).all()
        
        # Prepare data for display BEFORE closing session
        leads_data = []
        for lead in leads:
            leads_data.append({
                "_id": str(lead.id),
                "do_usunięcia": False,
                "Email": lead.email,
                "Imię": lead.first_name or "",
                "Nazwisko": lead.last_name or "",
                "Stanowisko": lead.position or "",
                "Firma": lead.company.name if lead.company else "",
                "Status": lead.status,
                "Notatki": lead.notes or "",
                "Data dodania": lead.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        
        session.close()
        
        if leads_data:
            # Interactive data editor
            df_display = pd.DataFrame(leads_data)
            edited_df = st.data_editor(
                df_display,
                use_container_width=True,
                hide_index=True,
                num_rows="fixed",
                key="leads_editor",
                column_config={
                    "_id": st.column_config.TextColumn(
                        "ID",
                        disabled=True,
                        width="small",
                    ),
                    "do_usunięcia": st.column_config.CheckboxColumn(
                        "🗑️ Usuń",
                        help="Zaznacz, aby trwale usunąć ten rekord z bazy",
                        default=False,
                        width="small",
                    ),
                    "Email": st.column_config.TextColumn(
                        "Email",
                        disabled=True,
                        width="medium",
                    ),
                    "Imię": st.column_config.TextColumn(
                        "Imię",
                        disabled=True,
                        width="small",
                    ),
                    "Nazwisko": st.column_config.TextColumn(
                        "Nazwisko",
                        disabled=True,
                        width="small",
                    ),
                    "Stanowisko": st.column_config.TextColumn(
                        "Stanowisko",
                        disabled=True,
                        width="medium",
                    ),
                    "Firma": st.column_config.TextColumn(
                        "Firma",
                        disabled=True,
                        width="medium",
                    ),
                    "Status": st.column_config.SelectboxColumn(
                        "Status",
                        options=["new", "sent", "opened", "replied", "bounced"],
                        width="small",
                    ),
                    "Notatki": st.column_config.TextColumn(
                        "Notatki",
                        help="Twoje prywatne notatki operacyjne",
                        width="large",
                        max_chars=500,
                    ),
                    "Data dodania": st.column_config.TextColumn(
                        "Data dodania",
                        disabled=True,
                        width="small",
                    ),
                },
            )
            
            # Summary statistics
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Łączna liczba leadów", len(leads_data))
            with col2:
                new_leads = sum(1 for lead in leads if lead.status == "new")
                st.metric("Nowe leads", new_leads)
            with col3:
                unique_companies = len(set(lead.company.name for lead in leads if lead.company))
                st.metric("Firmy", unique_companies)
            with col4:
                with_position = sum(1 for lead in leads if lead.position)
                st.metric("Ze stanowiskiem", with_position)

            st.markdown("---")
            if st.button("💾 Zapisz zmiany do bazy danych", type="primary", use_container_width=False):
                import uuid as uuid_lib
                from datetime import datetime as dt
                updated_count = 0
                deleted_count = 0
                errors = []

                sync_session = next(get_session_sync())
                try:
                    for _, row in edited_df.iterrows():
                        lead_id = uuid_lib.UUID(row["_id"])
                        lead_obj = sync_session.get(Lead, lead_id)
                        if lead_obj is None:
                            continue

                        if row["do_usunięcia"]:
                            sync_session.delete(lead_obj)
                            deleted_count += 1
                        else:
                            changed = False
                            new_status = row["Status"]
                            new_notes = row["Notatki"] if row["Notatki"] != "" else None
                            if lead_obj.status != new_status:
                                lead_obj.status = new_status
                                changed = True
                            if lead_obj.notes != new_notes:
                                lead_obj.notes = new_notes
                                changed = True
                            if changed:
                                lead_obj.updated_at = dt.utcnow()
                                updated_count += 1

                    sync_session.commit()
                except Exception as sync_err:
                    sync_session.rollback()
                    errors.append(str(sync_err))
                finally:
                    sync_session.close()

                if errors:
                    st.error(f"Błąd podczas zapisu: {errors[0]}")
                else:
                    parts = []
                    if updated_count:
                        parts.append(f"zaktualizowano {updated_count} rekord(ów)")
                    if deleted_count:
                        parts.append(f"usunięto {deleted_count} rekord(ów)")
                    if parts:
                        st.toast(f"✅ Zapisano: {', '.join(parts)}", icon="✅")
                    else:
                        st.toast("Brak zmian do zapisania.", icon="ℹ️")
                    st.rerun()

        else:
            st.info("Brak leadów w bazie danych. Zaimportuj dane w zakładce 'Import Danych (CSV)'.")
    
    except Exception as e:
        st.error(f"Błąd przy pobieraniu danych: {str(e)}")

# --- ZAKŁADKA 2: IMPORT PLIKÓW ---
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