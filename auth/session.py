"""
auth/session.py
Custom email/password auth (Supabase used as plain Postgres, not Supabase Auth).
Session state lives in st.session_state -- no tokens, no email verification.
"""
from __future__ import annotations

import bcrypt
import streamlit as st

from db import operations as db


class AuthError(Exception):
    pass


def signup(email: str, password: str, name: str, role: str) -> dict:
    """Creates a new profile. role must be 'client' or 'freelancer'."""
    if role not in ("client", "freelancer"):
        raise AuthError("Role must be 'client' or 'freelancer'")
    if not email or not password or not name:
        raise AuthError("Email, password, and name are required")

    existing = db.get_profile_by_email(email)
    if existing:
        raise AuthError("An account with this email already exists")

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    profile = db.save_profile({
        "email": email,
        "password_hash": password_hash,
        "name": name,
        "role": role,
    })
    if profile is None:
        raise AuthError("Failed to create account")
    return profile


def login(email: str, password: str) -> dict:
    """Verifies credentials, returns the profile row on success."""
    profile = db.get_profile_by_email(email)
    if profile is None:
        raise AuthError("Invalid email or password")

    stored_hash = profile.get("password_hash", "")
    if not stored_hash or not bcrypt.checkpw(password.encode(), stored_hash.encode()):
        raise AuthError("Invalid email or password")

    return profile


def login_and_set_session(email: str, password: str) -> dict:
    """Login + populate st.session_state in one call, for use directly from a form handler."""
    profile = login(email, password)
    st.session_state["user_id"] = profile["user_id"]
    st.session_state["role"] = profile["role"]
    st.session_state["name"] = profile["name"]
    st.session_state["email"] = profile["email"]
    return profile


def logout() -> None:
    for key in ("user_id", "role", "name", "email"):
        st.session_state.pop(key, None)


def is_logged_in() -> bool:
    return "user_id" in st.session_state


def require_login() -> None:
    """Call at the top of any protected page. Stops execution if not logged in."""
    if not is_logged_in():
        st.warning("Please log in to continue.")
        st.stop()


def current_user() -> dict:
    """Convenience accessor for the currently logged-in user's session fields."""
    require_login()
    return {
        "user_id": st.session_state["user_id"],
        "role": st.session_state["role"],
        "name": st.session_state["name"],
        "email": st.session_state["email"],
    }