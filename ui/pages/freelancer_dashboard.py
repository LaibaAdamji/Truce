"""
ui/pages/freelancer_dashboard.py
"""
import streamlit as st

from auth.session import current_user
from db import operations as db
from ui.components.stats import render_stats
from ui.components.project_card import render_project_card


def render() -> None:
    user = current_user()
    freelancer_profile = db.get_freelancer_profile_by_user(user["user_id"])

    st.title(f"Welcome back, {user['name']}")

    if not freelancer_profile:
        st.warning("No freelancer profile found for this account.")
        return

    projects = db.get_projects_by_freelancer(freelancer_profile["freelancer_profile_id"])

    render_stats(projects)

    st.markdown("### Assigned Projects")
    if not projects:
        st.info("No projects assigned to you yet.")
        return

    for project in sorted(projects, key=lambda p: p.get("created_at", ""), reverse=True):
        render_project_card(project, viewer_role="freelancer")