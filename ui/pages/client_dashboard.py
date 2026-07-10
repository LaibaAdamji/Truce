"""
ui/pages/client_dashboard.py
"""
import streamlit as st

from auth.session import current_user
from db import operations as db
from ui.components.stats import render_stats
from ui.components.project_card import render_project_card


def render() -> None:
    user = current_user()
    client_profile = db.get_client_profile_by_user(user["user_id"])

    st.title(f"Welcome back, {user['name']}")

    if not client_profile:
        st.warning("No client profile found for this account.")
        return

    if st.button("+ New Project"):
        st.session_state["page"] = "new_project"
        st.rerun()

    projects = db.get_projects_by_client(client_profile["client_profile_id"])

    render_stats(projects)

    st.markdown("### Your Projects")
    if not projects:
        st.info("No projects yet — click \"+ New Project\" to get started.")
        return

    for project in sorted(projects, key=lambda p: p.get("created_at", ""), reverse=True):
        render_project_card(project, viewer_role="client")