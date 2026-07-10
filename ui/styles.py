"""
SALES BOT — Premium Dark Theme.
All custom CSS lives here; call apply_custom_css() once from the entry point.
"""

import streamlit as st

_CUSTOM_CSS = """
<style>
/* ═══════════════════════════════════════════════════════
   SALES BOT — Premium Dark Theme
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

/* ── Dividers ── */
hr { border-color: rgba(255,255,255,.07) !important; margin: 4px 0 8px !important; }

/* ── Filter bar inputs — subtle fill ── */
div[data-testid="stTextInput"] input {
    background: rgba(255,255,255,.04) !important;
    border-radius: 8px !important;
}

/* ── Tag badges ── */
.tag-badge {
    display: inline-flex; align-items: center;
    padding: 1px 7px; border-radius: 99px;
    font-size: 0.62rem; font-weight: 700;
    letter-spacing: 0.05em; text-transform: uppercase;
    white-space: nowrap; margin: 1px 2px 1px 0;
}
.tag-jdd        { background: rgba(6,182,212,.12);   color: #22d3ee; border: 1px solid rgba(6,182,212,.30); }
.tag-omh        { background: rgba(249,115,22,.12);  color: #fb923c; border: 1px solid rgba(249,115,22,.30); }
.tag-confidence { background: rgba(34,197,94,.12);   color: #4ade80; border: 1px solid rgba(34,197,94,.30); }
.tag-default    { background: rgba(148,163,184,.12); color: #94a3b8; border: 1px solid rgba(148,163,184,.30); }

/* ── Text truncation (long names/emails/companies in table cells) ── */
.truncate-text {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    display: block;
    max-width: 100%;
}

/* ── Pagination bar ── */
.page-indicator {
    text-align: center;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    opacity: .55;
    line-height: 2.4;
    white-space: nowrap;
}
</style>
"""


def apply_custom_css() -> None:
    """Inject the dashboard theme. Call once per run, right after set_page_config."""
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)
