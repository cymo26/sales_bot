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

# 3. Podział na zakładki
tab_baza, tab_import = st.tabs(["📊 Baza Główna (Master)", "📥 Import Danych (CSV)"])

# --- ZAKŁADKA 1: GŁÓWNA BAZA ---
with tab_baza:
    st.header("Twoje Kontakty")
    
    # Create columns for filter options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search_email = st.text_input("Szukaj po email", "")
    with col2:
        search_name = st.text_input("Szukaj po imieniu/nazwisku", "")
    with col3:
        search_company = st.text_input("Szukaj po firmie", "")
    
    # Fetch leads from database
    try:
        from sqlalchemy.orm import joinedload
        
        session = next(get_session_sync())
        
        # Build query with eager loading of company
        query = session.query(Lead).options(joinedload(Lead.company)).join(Company, Lead.company_id == Company.id, isouter=True)
        
        # Apply filters
        if search_email:
            query = query.filter(Lead.email.ilike(f"%{search_email}%"))
        if search_name:
            query = query.filter(
                (Lead.first_name.ilike(f"%{search_name}%")) | 
                (Lead.last_name.ilike(f"%{search_name}%"))
            )
        if search_company:
            query = query.filter(Company.name.ilike(f"%{search_company}%"))
        
        # Get all leads
        leads = query.order_by(Lead.created_at.desc()).all()
        
        # Prepare data for display BEFORE closing session
        leads_data = []
        for lead in leads:
            leads_data.append({
                "Email": lead.email,
                "Imię": lead.first_name or "—",
                "Nazwisko": lead.last_name or "—",
                "Stanowisko": lead.position or "—",
                "Firma": lead.company.name if lead.company else "—",
                "Status": lead.status,
                "Data dodania": lead.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        
        session.close()
        
        if leads_data:
            # Display as dataframe
            df_display = pd.DataFrame(leads_data)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
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