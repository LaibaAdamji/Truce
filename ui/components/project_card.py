"""
ui/components/project_card.py
Renders a single project as a frosted-glass card with a status badge and
a "continue" action that routes the user to wherever that project needs
attention next. Used by both client_dashboard.py and freelancer_dashboard.py.

Visual styling for these cards lives in ui/theme.py, targeting the
Streamlit-generated container class via `st.container(key=...)`
(selector: div[class*="st-key-project_card"]).
"""
import streamlit as st

from ui.theme import status_badge_html

# Statuses considered "done" for routing purposes -- send straight to the
# contract page instead of negotiation.
_CONTRACT_STAGE = {"contract_generated", "signed", "completed"}

# Statuses where a freelancer still needs to set their price floor before
# anything else is useful.
_NEEDS_FREELANCER_SCOPING = {"draft", "requirements_extracted"}

_CTA_LABELS = {
    "draft": "Continue",
    "requirements_extracted": "Continue",
    "clarifications_pending": "Answer Questions",
    "pricing_ready": "Review",
    "negotiating": "Negotiate",
    "contract_generated": "View Contract",
    "signed": "View Contract",
    "completed": "View Contract",
    "cancelled": "View",
}


def _route_for(status: str, viewer_role: str) -> str:
    if status in _CONTRACT_STAGE:
        return "contract"
    if viewer_role == "freelancer" and status in _NEEDS_FREELANCER_SCOPING:
        return "freelancer_scoping"
    return "negotiation"


def _format_date(raw: str) -> str:
    # created_at typically arrives as an ISO timestamp from Supabase.
    if not raw:
        return ""
    return str(raw)[:10]


def render_project_card(project: dict, viewer_role: str) -> None:
    project_id = project.get("project_id", "")
    title = project.get("title") or "Untitled Project"
    status = project.get("status", "draft")
    created_at = _format_date(project.get("created_at", ""))
    rate = project.get("agreed_rate") or project.get("rate")

    with st.container(key=f"project_card_{project_id}"):
        col_main, col_action = st.columns([4, 1], vertical_alignment="center")

        with col_main:
            st.markdown(f"##### {title}")
            meta_bits = [status_badge_html(status)]
            st.markdown(" ".join(meta_bits), unsafe_allow_html=True)

            caption_parts = []
            if created_at:
                caption_parts.append(f"Created {created_at}")
            if rate:
                caption_parts.append(f"${rate:.2f}/hr")
            if caption_parts:
                st.markdown(
                    f'<p class="truce-secondary" style="margin:6px 0 0 0; font-size:0.85rem;">'
                    f'{" · ".join(caption_parts)}</p>',
                    unsafe_allow_html=True,
                )

        with col_action:
            label = _CTA_LABELS.get(status, "View")
            if st.button(f"{label} →", key=f"view_project_{project_id}"):
                st.session_state["active_project_id"] = project_id
                st.session_state["page"] = _route_for(status, viewer_role)
                st.rerun()