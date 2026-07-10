"""
app.py
Routing entry point: login gate, then dispatch by role.
Each real page lives in ui/pages/ -- this file only wires them together.
"""
import streamlit as st

from ui.theme import apply_theme, render_theme_toggle
from auth.session import is_logged_in, current_user, logout
from ui.pages import login as login_page
from ui.pages import client_dashboard, freelancer_dashboard, new_project, negotiation, contract, freelancer_scoping


st.set_page_config(page_title="Truce", page_icon=":handshake:", layout="wide")

if "theme_mode" not in st.session_state:
    st.session_state["theme_mode"] = "light"

apply_theme(st.session_state["theme_mode"])

if not is_logged_in():
    login_page.render()
    st.stop()

user = current_user()

with st.sidebar:
    initial = (user["name"] or "?")[0].upper()
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:1.2rem;">
            <div style="width:38px; height:38px; border-radius:50%; background:var(--accent-amber);
                        color:#fff; display:flex; align-items:center; justify-content:center;
                        font-weight:700; font-size:1rem; flex-shrink:0;">
                {initial}
            </div>
            <div>
                <p style="margin:0; font-weight:600; line-height:1.2;">{user['name']}</p>
                <p class="truce-secondary" style="margin:0; font-size:0.8rem;">{user['role'].title()}</p>
            </div>
        </div>
        <hr style="border-color: var(--border); margin: 0 0 1rem 0;">
        """,
        unsafe_allow_html=True,
    )
    render_theme_toggle()
    st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
    if st.button("Log Out"):
        logout()
        st.rerun()

page = st.session_state.get("page", "dashboard")

if user["role"] == "client":
    if page == "new_project":
        new_project.render()
    elif page == "negotiation":
        negotiation.render()
    elif page == "contract":
        contract.render()
    else:
        client_dashboard.render()
else:
    if page == "freelancer_scoping":
        freelancer_scoping.render()
    elif page == "negotiation":
        negotiation.render()
    elif page == "contract":
        contract.render()
    else:
        freelancer_dashboard.render()