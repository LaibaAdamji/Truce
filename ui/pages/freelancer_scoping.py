"""
ui/pages/freelancer_scoping.py
Shows the finalized project requirements (so the freelancer knows what
they're pricing) then collects a rate expectation and hands off to the
Freelancer Agent to compute a price floor.
"""
import streamlit as st
from db import operations as db
from agents import freelancer_agent


def _render_requirements(version_id: str) -> None:
    st.markdown("### Project Requirements")

    requirements = db.get_requirements_by_version(version_id)
    if not requirements:
        st.markdown(
            """
            <div class="truce-empty-state">
                <div class="truce-empty-icon">📋</div>
                <p style="margin:0;">No itemized requirements on file for this project yet.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    budget_items = [r for r in requirements if r.get("type") == "budget"]
    scope_items = [r for r in requirements if r.get("type") != "budget"]

    if budget_items:
        for b in budget_items:
            st.markdown(
                f"""
                <div class="truce-card-glass" style="margin-bottom:12px;">
                    <p class="truce-secondary" style="margin:0; font-size:0.85rem;">Client Budget</p>
                    <p style="font-size:1.4rem; font-weight:600; margin:4px 0 0 0;">{b.get('value', '')}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if scope_items:
        for req in scope_items:
            st.markdown(
                f"""
                <div class="truce-card" style="margin-bottom:10px; padding:1rem 1.25rem;">
                    <p style="margin:0;">{req.get('value', str(req))}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)


def render() -> None:
    project_id = st.session_state.get("active_project_id")
    if not project_id:
        st.warning("No project selected.")
        return
    project = db.get_project(project_id)
    version = db.get_latest_version(project_id)
    st.title(project.get("title", "Project"))

    if version:
        _render_requirements(version["version_id"])
        st.markdown("---")

    floor = db.get_price_floor_by_version(version["version_id"]) if version else None
    if floor:
        st.success(f"Price floor already set: ${floor['amount']:.2f}/hr")
        if st.button("Go to Negotiation →", type="primary"):
            st.session_state["page"] = "negotiation"
            st.rerun()
        return

    rate = st.number_input("Your rate expectation ($/hr)", min_value=0.0, step=1.0)
    if st.button("Submit", disabled=not rate):
        user = st.session_state
        fp = db.get_freelancer_profile_by_user(user["user_id"])
        with st.spinner("Freelancer Agent reasoning price floor..."):
            try:
                freelancer_agent.compute_price_floor(
                    project_id=project_id,
                    version_id=version["version_id"],
                    freelancer_profile_id=fp["freelancer_profile_id"],
                    rate_expectation=rate,
                )
            except Exception as e:
                st.error(f"Failed: {e}")
                return
        st.session_state["page"] = "negotiation"
        st.rerun()