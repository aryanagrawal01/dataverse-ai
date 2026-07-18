"""Auth gating for pages."""

import streamlit as st

from dataverse.schemas.auth import UserDTO
from dataverse.services import auth_service
from dataverse.ui import state
from dataverse.utils.errors import SessionExpiredError


def resolve_user() -> UserDTO | None:
    """Return the signed-in user, clearing state on dead sessions."""
    token = state.get_session_token()
    if token is None:
        return None
    try:
        return auth_service.current_user(token)
    except SessionExpiredError:
        state.clear_all()
        st.toast("Your session expired — please sign in again.", icon="🔒")
        return None
