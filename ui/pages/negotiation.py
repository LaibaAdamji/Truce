"""
ui/pages/negotiation.py
Shows price floor reasoning + comparables, runs/displays the mediator's
negotiation, and surfaces the final outcome. Reads project_id from
st.session_state["active_project_id"] (set by project_card / dashboard).

Calls into agents.freelancer_agent / agents.mediator_agent directly --
no backend logic here, this page only orchestrates + visualizes.
"""
import streamlit as st

from db import operations as db
from agents import mediator_agent
from ui.theme import status_badge_html


def _back_to_dashboard() -> None:
    st.session_state["page"] = "dashboard"
    st.session_state.pop("active_project_id", None)


def render() -> None:
    project_id = st.session_state.get("active_project_id")
    if not project_id:
        st.warning("No project selected.")
        if st.button("← Back to Dashboard"):
            _back_to_dashboard()
            st.rerun()
        return

    project = db.get_project(project_id)
    if not project:
        st.error("Project not found.")
        return

    version = db.get_latest_version(project_id)
    version_id = version["version_id"] if version else None

    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("←", help="Back to dashboard"):
            _back_to_dashboard()
            st.rerun()
    with col_title:
        st.title(project.get("title", "Project"))
        st.markdown(status_badge_html(project.get("status", "draft")), unsafe_allow_html=True)

    st.markdown("---")

    _render_price_floor_section(version_id)
    st.markdown("---")
    _render_negotiation_section(project_id, version_id)


def _render_empty_state(icon: str, text: str) -> None:
    st.markdown(
        f"""
        <div class="truce-empty-state">
            <div class="truce-empty-icon">{icon}</div>
            <p class="truce-secondary" style="margin:0;">{text}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_price_floor_section(version_id: str | None) -> None:
    st.markdown("### Market Research & Price Floor")

    if not version_id:
        st.info("No project version found yet.")
        return

    floor = db.get_price_floor_by_version(version_id)
    if not floor:
        _render_empty_state(
            "📊",
            "Price floor hasn't been computed yet. This happens automatically once a freelancer is assigned.",
        )
        return

    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(
            f"""
            <div class="truce-card-glass">
                <p class="truce-secondary" style="margin:0; font-size:0.85rem;">Price Floor</p>
                <p style="font-size:2rem; font-weight:600; margin:4px 0;">${floor['amount']:.2f}/hr</p>
                <p class="truce-secondary" style="margin:0; font-size:0.8rem;">
                    Confidence: {floor.get('confidence', 0) * 100:.0f}%
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="truce-card"><p style="margin:0;">{floor.get("reasoning", "")}</p></div>',
            unsafe_allow_html=True,
        )

    comparables = db.get_comparables(floor["price_floor_id"])
    if comparables:
        with st.expander(f"View {len(comparables)} comparable rates used"):
            for c in comparables:
                st.markdown(f"- {c['text']}")


def _render_negotiation_section(project_id: str, version_id: str | None) -> None:
    st.markdown("### Negotiation")

    negotiation = db.get_negotiation_state(project_id)

    if not negotiation:
        _render_empty_state("🤝", "Negotiation hasn't started yet.")
        if version_id and st.button("Start Negotiation", type="primary"):
            with st.spinner("Mediator is working through offers..."):
                try:
                    mediator_agent.run_negotiation(project_id, version_id)
                except Exception as e:
                    st.error(f"Negotiation failed to start: {e}")
                    return
            st.rerun()
        return

    _render_negotiation_timeline(negotiation)


def _render_negotiation_timeline(negotiation: dict) -> None:
    rounds = db.get_negotiation_rounds(negotiation["negotiation_id"])
    status = negotiation.get("status", "open")

    status_labels = {
        "open": ("In progress", "truce-badge-active"),
        "converged": ("Agreement reached", "truce-badge-success"),
        "capped_no_deal": ("No deal reached", "truce-badge-warning"),
    }
    label, badge_class = status_labels.get(status, ("Unknown", "truce-badge-pending"))

    st.markdown(
        f'<span class="truce-badge {badge_class}">{label}</span>',
        unsafe_allow_html=True,
    )

    if rounds:
        st.markdown("<br>", unsafe_allow_html=True)
        for i, r in enumerate(rounds):
            delay = f"{i * 0.06:.2f}s"
            offer_html = (
                f'<div class="truce-bubble truce-bubble-offer" style="animation-delay:{delay};">'
                f'<span class="truce-round-marker">{r["round_number"]}</span>'
                f'${r["offer"]:.2f}/hr</div>'
            )
            message_html = (
                f'<div class="truce-bubble truce-bubble-mediator" style="animation-delay:{delay};">'
                f'{r.get("message", "")}</div>'
            )
            st.markdown(offer_html, unsafe_allow_html=True)
            st.markdown(message_html, unsafe_allow_html=True)

    if status == "converged":
        st.markdown(
            f"""
            <div class="truce-card-glass" style="margin-top:16px; text-align:center;">
                <p class="truce-secondary" style="margin:0;">Final agreed rate</p>
                <p style="font-size:2.4rem; font-weight:600; margin:4px 0;">
                    ${negotiation['current_offer']:.2f}/hr
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Ready to generate the contract? Head to the Contract tab.")
        if st.button("Go to Contract →", type="primary"):
            st.session_state["page"] = "contract"
            st.rerun()
    elif status == "capped_no_deal":
        st.markdown(
            '<p class="truce-secondary">The client ceiling and freelancer floor '
            "couldn't converge within the round limit.</p>",
            unsafe_allow_html=True,
        )
    elif status == "open" and rounds:
        # Round cap not yet reached but loop returned mid-negotiation --
        # shouldn't normally happen since run_negotiation runs to
        # completion synchronously, but guard the UI state anyway.
        st.markdown(
            '<p class="truce-loading-text">Negotiation in progress...</p>',
            unsafe_allow_html=True,
        )