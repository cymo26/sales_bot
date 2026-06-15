import streamlit as st
import pandas as pd

# Na razie komentujemy importy z bazy, żeby upewnić się, że sam UI odpala bez błędów
# from app.core.database import get_session, engine
# from app.models.models import Lead, Company

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
    st.info("Tutaj wkrótce podepniemy zapytanie SQL, które wyświetli Twoją bazę z PostgreSQL w interaktywnej tabeli.")
    st.info("skibidi sigma beng beng")
    # Miejsce na docelową tabelę z filtrami

# --- ZAKŁADKA 2: IMPORT PLIKÓW ---
with tab_import:
    st.header("Importuj nowe kontakty")
    st.markdown("Wgraj plik CSV (np. z Eventory lub Livespace), aby dodać rekordy do bazy.")
    
    uploaded_file = st.file_uploader("Przeciągnij i upuść plik CSV tutaj", type=["csv"])
    
    if uploaded_file is not None:
        # Odczyt pliku do pandas DataFrame (tylko do podglądu)
        df = pd.read_csv(uploaded_file)
        
        st.success(f"Pomyślnie wczytano plik: {uploaded_file.name}")
        st.markdown("**Podgląd pierwszych 5 wierszy:**")
        st.dataframe(df.head())
        
        # Przycisk, który docelowo uruchomi Pydantic i zapis do PostgreSQL
        if st.button("Zapisz do bazy PostgreSQL", type="primary"):
            st.warning("Mechanizm czyszczenia Pydantic i ochrony przed duplikatami podepniemy w kolejnym kroku!")