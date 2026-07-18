"""Typed accessors over st.session_state.

All session-state keys are defined here; pages never touch raw string keys.
"""

import streamlit as st

_KEY_SESSION_TOKEN = "dv_session_token"
_KEY_ACTIVE_PROJECT = "dv_active_project_id"
_KEY_NAV_PAGE = "dv_nav_page"


def get_session_token() -> str | None:
    return st.session_state.get(_KEY_SESSION_TOKEN)


def set_session_token(token: str | None) -> None:
    if token is None:
        st.session_state.pop(_KEY_SESSION_TOKEN, None)
    else:
        st.session_state[_KEY_SESSION_TOKEN] = token


def get_active_project_id() -> str | None:
    return st.session_state.get(_KEY_ACTIVE_PROJECT)


def set_active_project_id(project_id: str | None) -> None:
    if project_id is None:
        st.session_state.pop(_KEY_ACTIVE_PROJECT, None)
    else:
        st.session_state[_KEY_ACTIVE_PROJECT] = project_id


def get_nav_page(default: str = "home") -> str:
    return st.session_state.get(_KEY_NAV_PAGE, default)


def set_nav_page(page: str) -> None:
    st.session_state[_KEY_NAV_PAGE] = page


def clear_all() -> None:
    """Full logout: wipe everything we own."""
    for key in (_KEY_SESSION_TOKEN, _KEY_ACTIVE_PROJECT, _KEY_NAV_PAGE):
        st.session_state.pop(key, None)
