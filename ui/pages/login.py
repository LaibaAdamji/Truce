"""
ui/pages/login.py
Login + signup screen. On signup, also creates the role-specific
profile row (client_profiles or freelancer_profiles).
"""
import streamlit as st

from auth.session import signup, login_and_set_session, AuthError
from db import operations as db


def render() -> None:
    _inject_login_layout()

    st.markdown('<div class="truce-auth-wrap">', unsafe_allow_html=True)
    st.markdown(
        """
        <div style="text-align:center; margin-bottom: 1.75rem;">
            <h1 style="margin-bottom:0.2rem;">🤝 Truce</h1>
            <p class="truce-secondary" style="margin:0;">Turn a messy brief into a signed contract.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="truce-card truce-auth-card">', unsafe_allow_html=True)
    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    with tab_login:
        _render_login()

    with tab_signup:
        _render_signup()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _inject_login_layout() -> None:
    st.markdown(
        """
        <style>
        .truce-auth-wrap {
            max-width: 460px;
            margin: 3rem auto 0 auto;
        }
        .truce-auth-card {
            padding: 2rem 2rem 1.5rem 2rem;
        }
        .truce-auth-card .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
        }
        .truce-auth-card .stTabs [data-baseweb="tab"] {
            border-radius: 10px;
            padding: 6px 4px;
        }
        .truce-auth-card .stFormSubmitButton > button {
            width: 100%;
            margin-top: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_login() -> None:
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", type="primary")

    if submitted:
        try:
            login_and_set_session(email, password)
            st.rerun()
        except AuthError as e:
            st.error(str(e))


def _render_signup() -> None:
    role = st.radio(
        "I am a...", ["client", "freelancer"],
        horizontal=True, key="signup_role", index=None,
    )
    if role is None:
        st.info("Select a role to continue.")
        return

    with st.form("signup_form"):
        name = st.text_input("Full name")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")

        company_name = None
        industry = None
        skills = None
        years_experience = None
        rate_expectation = None

        if role == "client":
            company_name = st.text_input("Company name (optional)")
            industry = st.text_input("Industry (optional)")
        else:
            skills_raw = st.text_input("Skills (comma-separated, e.g. React, Node.js)")
            skills = [s.strip() for s in skills_raw.split(",") if s.strip()] if skills_raw else []
            years_experience = st.number_input("Years of experience", min_value=0, step=1)
            rate_expectation = st.number_input("Rate expectation ($/hr)", min_value=0.0, step=1.0)

        submitted = st.form_submit_button("Create Account", type="primary")

    if submitted:
        try:
            profile = signup(email=email, password=password, name=name, role=role)
            user_id = profile["user_id"]

            if role == "client":
                db.save_client_profile({
                    "user_id": user_id,
                    "company_name": company_name or None,
                    "industry": industry or None,
                })
            else:
                db.save_freelancer_profile({
                    "user_id": user_id,
                    "skills": skills or [],
                    "years_experience": int(years_experience or 0),
                    "rate_expectation": float(rate_expectation or 0.0),
                })

            st.success("Account created — please log in.")
        except AuthError as e:
            st.error(str(e))