"""
Shared render helpers: tag pills, the lead table (used by both the Kontakty
and Baza Firm tabs), and pagination controls.

The lead-row renderer returns True when the "Szczegóły" button was clicked so
the calling tab can open the profile dialog — components never import dialogs,
which keeps the import graph acyclic.
"""

from html import escape as h

import streamlit as st

from ui.constants import AVAILABLE_TAGS, STATUS_CLASS, status_label

# Column layout of the lead table; the Kontakty tab prepends a checkbox column.
_CHECKBOX_WEIGHT = [0.4]
_LEAD_WEIGHTS = [2, 2.3, 1.8, 2, 1.3, 1, 1.5, 0.8, 1]
_LEAD_HEADERS = ["Imie i Nazwisko", "Email", "Firma", "Stanowisko",
                 "Lokalizacja", "Status", "Tagi", "LN", ""]


def render_tags(tags_str: str) -> str:
    """Comma-separated tags → HTML pills (empty string when no tags)."""
    if not tags_str:
        return ""
    pills = []
    for tag in [t.strip() for t in tags_str.split(",") if t.strip()]:
        css = f"tag-{tag.lower()}" if tag.upper() in AVAILABLE_TAGS else "tag-default"
        pills.append(f"<span class='tag-badge {css}'>{h(tag)}</span>")
    return "".join(pills)


def _small_caps(col, label: str) -> None:
    col.markdown(
        f"<small style='font-weight:700;text-transform:uppercase;"
        f"letter-spacing:.06em;opacity:.45'>{label}</small>",
        unsafe_allow_html=True,
    )


def _set_all_selection(lead_ids) -> None:
    """on_change of the master checkbox: mirror its value onto every row
    checkbox of the current page (runs before widgets render, so it sticks)."""
    value = st.session_state.get("select_all_leads", False)
    for lead_id in lead_ids:
        st.session_state[f"del_{lead_id}"] = value


def render_select_all(lead_ids) -> None:
    """Clearly labelled master checkbox, rendered above the table (the header
    column is too narrow for a visible label)."""
    st.checkbox(
        "Zaznacz wszystkie",
        key="select_all_leads",
        help="Zaznacza / odznacza wszystkie kontakty na tej stronie",
        on_change=_set_all_selection,
        args=(tuple(lead_ids),),
    )


def _truncated_cell(col, value: str, *, bold: bool = False,
                    style: str = "", prefix: str = "") -> None:
    """Ellipsis-truncated cell; title= gives the native full-text tooltip."""
    safe = h(str(value))
    inner = f"<b>{safe}</b>" if bold else safe
    style_attr = f" style='{style}'" if style else ""
    col.markdown(
        f"{prefix}<div class='truncate-text' title=\"{safe}\"{style_attr}>{inner}</div>",
        unsafe_allow_html=True,
    )


def render_lead_table_header(with_checkbox: bool = False) -> None:
    weights = (_CHECKBOX_WEIGHT if with_checkbox else []) + _LEAD_WEIGHTS
    headers = ([""] if with_checkbox else []) + _LEAD_HEADERS
    for col, label in zip(st.columns(weights), headers):
        _small_caps(col, label)
    st.divider()


def render_lead_row(row: dict, key_prefix: str = "", with_checkbox: bool = False) -> bool:
    """One lead row. Returns True when 'Szczegóły' was clicked this run.
    The checkbox (Kontakty bulk delete) uses the session key f"del_{id}"."""
    weights = (_CHECKBOX_WEIGHT if with_checkbox else []) + _LEAD_WEIGHTS
    cols = st.columns(weights)
    if with_checkbox:
        cols[0].checkbox("Zaznacz", key=f"del_{row['id']}", label_visibility="collapsed")
        cols = cols[1:]
    c_name, c_email, c_co, c_pos, c_loc, c_status, c_tags, c_li, c_act = cols

    _truncated_cell(c_name, row["full_name"], bold=True,
                    prefix="<span class='row-hover-marker'></span>")
    _truncated_cell(c_email, row["email"],
                    style="font-size:.88rem;font-family:ui-monospace,monospace;color:#a3a8b8")
    _truncated_cell(c_co, row["company"])
    _truncated_cell(c_pos, row["position"])
    _truncated_cell(c_loc, row["location"])
    c_status.markdown(
        f"<span class='lbadge {STATUS_CLASS.get(row['status'], 'lb-nowy')}'>"
        f"{h(status_label(row['status']))}</span>",
        unsafe_allow_html=True,
    )
    tags_html = render_tags(row["tags"])
    c_tags.markdown(tags_html or "<span style='opacity:.2'>—</span>",
                    unsafe_allow_html=True)
    if row["linkedin_url"]:
        c_li.link_button("🔗", row["linkedin_url"], use_container_width=True)
    else:
        c_li.markdown("<span style='opacity:.2;font-size:.8rem'>—</span>",
                      unsafe_allow_html=True)
    return c_act.button("Szczegóły", key=f"btn_{key_prefix}{row['id']}")


# ── Pagination ───────────────────────────────────────────────────────────────

def current_page(state_key: str) -> int:
    """Requested page for this table (1-based). Clamp against the fetch result."""
    return max(1, int(st.session_state.get(state_key, 1)))


def reset_page(state_key: str) -> None:
    """Back to page 1 — call whenever filters change."""
    st.session_state[state_key] = 1


def _set_page(state_key: str, page: int) -> None:
    st.session_state[state_key] = page


def render_pagination(state_key: str, page: int, pages: int, total: int,
                      noun: str = "rekordów") -> None:
    """Prev / 'Strona X z Y' / Next. Page changes happen in on_click callbacks,
    which run before the rerun — no st.rerun() needed (and none to get caught
    by a surrounding try/except)."""
    if pages <= 1 and total <= 0:
        return
    st.session_state[state_key] = page  # persist the clamped value
    prev_col, info_col, next_col = st.columns([1, 3, 1])
    prev_col.button(
        "← Poprzednia", key=f"{state_key}_prev", use_container_width=True,
        disabled=page <= 1, on_click=_set_page, args=(state_key, page - 1),
    )
    info_col.markdown(
        f"<div class='page-indicator'>Strona {page} z {pages} · {total} {noun}</div>",
        unsafe_allow_html=True,
    )
    next_col.button(
        "Następna →", key=f"{state_key}_next", use_container_width=True,
        disabled=page >= pages, on_click=_set_page, args=(state_key, page + 1),
    )
