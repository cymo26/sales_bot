"""Shared vocabulary for the API layer — duplicated from db/queries.py and
ui/constants.py rather than imported, so importing app.api never pulls in
Streamlit (db/queries.py imports streamlit at module level for @st.cache_*).
Keep these in sync with db/queries.py and ui/constants.py if either changes.
"""

LEADS_PAGE_SIZE = 50
COMPANIES_PAGE_SIZE = 20

CANONICAL_STATUSES = ["new", "sent", "opened", "replied", "bounced"]

LEGACY_STATUS_MAP = {
    "nowy": "new",
    "wysłany": "sent",
    "otwarty": "opened",
    "odpowiedział": "replied",
    "odbitka": "bounced",
}

DEFAULT_INDUSTRIES = [
    "FinTech & Banking",
    "HealthTech & Pharma",
    "E-commerce & Retail",
    "Telecommunications",
    "Automotive & IoT",
    "Software Houses / IT",
]

AVAILABLE_TAGS = ["JDD", "OMH", "CONFIDENCE"]
