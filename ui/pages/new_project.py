"""
ui/pages/new_project.py
Client creates a project: title + brief (chat-style), Client Agent extracts
requirements, any clarification gaps are asked back to the client in a loop,
then scope is finalized and an optional freelancer is assigned.
"""
import streamlit as st

from auth.session import current_user
from db import operations as db
from agents import client_agent

# NOTE: no "pending_freelancer_input" status exists in the current Project.status
# enum -- using "requirements_extracted" to represent "scope done, waiting on
# freelancer to act" rather than touching the schema/DB constraint this late.
# Flagging as a known simplification, not a bug.

_STEPS = [
    ("brief", "Brief"),
    ("clarify", "Clarify"),
    ("assign", "Assign"),
    ("done", "Done"),
]


def _reset_flow() -> None:
    for key in ("np_step", "np_project_id", "np_version_id", "np_pending_gaps", "np_scope_done"):
        st.session_state.pop(key, None)


def _render_step_progress(current_step: str) -> None:
    step_keys = [s[0] for s in _STEPS]
    current_idx = step_keys.index(current_step) if current_step in step_keys else 0

    pills = []
    for i, (key, label) in enumerate(_STEPS):
        if i < current_idx:
            style = "background: var(--accent-olive); color:#fff;"
        elif i == current_idx:
            style = "background: var(--accent-amber); color:#fff;"
        else:
            style = "background: var(--surface); color: var(--text-muted); border: 1px solid var(--border);"
        pills.append(
            f'<span style="{style} padding:5px 14px; border-radius:999px; '
            f'font-size:0.78rem; font-weight:600; margin-right:6px;">{i + 1}. {label}</span>'
        )

    st.markdown(
        f'<div style="margin-bottom:1.5rem;">{"".join(pills)}</div>',
        unsafe_allow_html=True,
    )


def render() -> None:
    user = current_user()
    client_profile = db.get_client_profile_by_user(user["user_id"])
    if not client_profile:
        st.warning("No client profile found for this account.")
        return

    st.title("New Project")
    if st.button("← Back to Dashboard"):
        _reset_flow()
        st.session_state["page"] = "dashboard"
        st.rerun()

    step = st.session_state.get("np_step", "brief")
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    _render_step_progress(step)

    st.markdown('<div class="truce-card">', unsafe_allow_html=True)
    if step == "brief":
        _render_brief_step(client_profile["client_profile_id"])
    elif step == "clarify":
        _render_clarify_step()
    elif step == "assign":
        _render_assign_step()
    elif step == "done":
        _render_done_step()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_brief_step(client_profile_id: str) -> None:
    st.caption("Describe the project in your own words — the more detail, the fewer follow-up questions.")

    title = st.text_input("Project title")
    brief_text = st.text_area(
        "Project brief",
        height=200,
        placeholder="e.g. Need a React developer for a 3-week e-commerce checkout flow, budget ~$3000...",
    )

    if st.button("Submit Brief", disabled=not (title and brief_text), type="primary"):
        with st.spinner("Client Agent is reading your brief..."):
            try:
                project, version = client_agent.create_project(
                    client_profile_id=client_profile_id,
                    title=title,
                    brief_text=brief_text,
                )
                gaps = client_agent.extract_requirements(
                    project_id=str(project.project_id),
                    version_id=str(version.version_id),
                    brief_text=brief_text,
                )
            except Exception as e:
                st.error(f"Something went wrong extracting requirements: {e}")
                return

        st.session_state["np_project_id"] = str(project.project_id)
        st.session_state["np_version_id"] = str(version.version_id)

        if gaps:
            st.session_state["np_step"] = "clarify"
        else:
            st.session_state["np_step"] = "assign"
        st.rerun()


def _render_clarify_step() -> None:
    project_id = st.session_state["np_project_id"]
    version_id = st.session_state["np_version_id"]

    clarifications = client_agent.get_clarifications_for_version(version_id)
    pending = [c for c in clarifications if c.status == "pending"]

    if not pending:
        st.session_state["np_step"] = "assign"
        st.rerun()
        return

    st.markdown("### A couple of quick questions")
    st.caption("The Client Agent needs a bit more detail before finalizing scope.")
    st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

    answers: dict[str, str] = {}
    with st.form("clarify_form"):
        for c in pending:
            answers[str(c.gap_id)] = st.text_input(c.question_text, key=f"clarify_{c.clarification_id}")
        submitted = st.form_submit_button("Submit Answers", type="primary")

    if submitted:
        answers = {gid: text for gid, text in answers.items() if text.strip()}
        if not answers:
            st.warning("Please answer at least one question.")
            return

        with st.spinner("Client Agent is updating requirements..."):
            try:
                new_gaps = client_agent.submit_clarifications(
                    project_id=project_id,
                    version_id=version_id,
                    answers=answers,
                    answered_by=st.session_state["user_id"],
                )
            except Exception as e:
                st.error(f"Something went wrong: {e}")
                return

        if new_gaps:
            st.rerun()  # more pending clarifications will be picked up above
        else:
            st.session_state["np_step"] = "assign"
            st.rerun()


def _render_assign_step() -> None:
    project_id = st.session_state["np_project_id"]
    version_id = st.session_state["np_version_id"]

    st.success("Requirements finalized.")

    if "np_scope_done" not in st.session_state:
        with st.spinner("Finalizing scope..."):
            try:
                client_agent.finalize_scope(project_id=project_id, version_id=version_id)
                st.session_state["np_scope_done"] = True
            except Exception as e:
                st.error(f"Something went wrong finalizing scope: {e}")
                return

    st.markdown("### Assign a Freelancer")
    st.caption("Paste the freelancer's ID to connect them to this project (optional — you can also do this later).")
    st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

    freelancer_id = st.text_input("Freelancer ID")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Assign & Continue", disabled=not freelancer_id, type="primary"):
            fp = db.get_freelancer_profile(freelancer_id)
            if not fp:
                st.error("No freelancer found with that ID.")
                return
            try:
                client_agent.assign_freelancer(project_id, freelancer_id)
            except Exception as e:
                st.error(f"Failed to assign freelancer: {e}")
                return
            st.session_state["np_step"] = "done"
            st.rerun()
    with col2:
        if st.button("Skip for now"):
            st.session_state["np_step"] = "done"
            st.rerun()


def _render_done_step() -> None:
    st.success("Project created! You'll see it on your dashboard.")
    if st.button("Go to Dashboard", type="primary"):
        _reset_flow()
        st.session_state["page"] = "dashboard"
        st.rerun()