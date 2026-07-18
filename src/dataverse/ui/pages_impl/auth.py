"""Sign-in / registration page."""

import streamlit as st

from dataverse.services import auth_service
from dataverse.ui import state
from dataverse.ui.components.empty_states import hero
from dataverse.ui.theme import brand_mark
from dataverse.utils.errors import DataVerseError


def render() -> None:
    with st.sidebar:
        brand_mark()
        st.caption("Sign in to continue")

    hero(
        badge="AI-powered Business Intelligence",
        title="Welcome to DataVerse AI",
        subtitle="Sign in or create an account to turn your spreadsheets into insight.",
    )

    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        tab_login, tab_register = st.tabs(["Sign in", "Create account"])

        with tab_login, st.form("login_form", border=False):
            email = st.text_input("Email", key="login_email", autocomplete="email")
            password = st.text_input(
                "Password", type="password", key="login_pw", autocomplete="current-password"
            )
            if st.form_submit_button("Sign in", type="primary", use_container_width=True):
                _attempt(lambda: auth_service.login(email, password))

        with tab_register, st.form("register_form", border=False):
            name = st.text_input("Name", key="reg_name", autocomplete="name")
            email_r = st.text_input("Email", key="reg_email", autocomplete="email")
            password_r = st.text_input(
                "Password",
                type="password",
                key="reg_pw",
                autocomplete="new-password",
                help="At least 8 characters, including a number.",
            )
            if st.form_submit_button("Create account", type="primary", use_container_width=True):
                _attempt(lambda: auth_service.register(email_r, password_r, name or None))


def _attempt(action) -> None:
    try:
        result = action()
    except DataVerseError as exc:
        st.error(exc.user_message)
        return
    state.set_session_token(result.token)
    st.rerun()
