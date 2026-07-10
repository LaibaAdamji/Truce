"""
ui/components/stats.py
Renders a row of frosted-glass summary tiles above the project list on
both dashboards. Pure presentation -- takes whatever project dicts the
dashboard already fetched, no extra DB calls.
"""
import streamlit as st

_IN_PROGRESS_STATUSES = {
    "requirements_extracted",
    "clarifications_pending",
    "pricing_ready",
    "negotiating",
}
_COMPLETE_STATUSES = {"contract_generated", "signed", "completed"}


def _tile(label: str, value: str) -> str:
    return f"""
        <div class="truce-card-glass" style="text-align:center; padding:1.1rem;">
            <p class="truce-secondary" style="margin:0; font-size:0.8rem; letter-spacing:0.02em;">{label}</p>
            <p style="font-size:2.1rem; font-weight:700; margin:6px 0 0 0;">{value}</p>
        </div>
    """


def render_stats(projects: list[dict]) -> None:
    if not projects:
        return

    total = len(projects)
    in_progress = sum(1 for p in projects if p.get("status") in _IN_PROGRESS_STATUSES)
    completed = sum(1 for p in projects if p.get("status") in _COMPLETE_STATUSES)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(_tile("Total Projects", str(total)), unsafe_allow_html=True)
    with col2:
        st.markdown(_tile("In Progress", str(in_progress)), unsafe_allow_html=True)
    with col3:
        st.markdown(_tile("Completed", str(completed)), unsafe_allow_html=True)

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)