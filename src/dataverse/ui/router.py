"""Session-aware navigation: unauthenticated users see the auth page; signed-in
users get the app shell (sidebar nav + routed page bodies)."""

import streamlit as st

from dataverse.schemas.auth import UserDTO
from dataverse.services import auth_service
from dataverse.ui import state
from dataverse.ui.errors import page_boundary
from dataverse.ui.guards import resolve_user
from dataverse.ui.pages_impl import auth, projects, upload
from dataverse.ui.theme import brand_mark
from dataverse.utils.logging import bind_context

_NAV = [
    ("projects", "🗂️  Projects"),
    ("upload", "📤  Upload"),
]


@page_boundary
def route() -> None:
    user = resolve_user()
    if user is None:
        auth.render()
        return

    bind_context(user_id=user.id)
    _sidebar(user)

    page = state.get_nav_page(default="projects")
    if page == "upload":
        upload.render(user)
    elif page == "project":
        _project_shell(user)
    else:
        projects.render(user)


def _sidebar(user: UserDTO) -> None:
    with st.sidebar:
        brand_mark()
        for key, label in _NAV:
            if st.button(label, key=f"nav_{key}"):
                state.set_nav_page(key)
                state.set_active_project_id(None)
                st.rerun()
        st.divider()
        st.caption(user.display_name or user.email)
        if st.button("⏻  Sign out", key="nav_logout"):
            token = state.get_session_token()
            if token:
                auth_service.logout(token)
            state.clear_all()
            st.rerun()


def _project_shell(user: UserDTO) -> None:
    """Project workspace. Tabs (health, dashboard, …) arrive with M2+."""
    project_id = state.get_active_project_id()
    if project_id is None:
        state.set_nav_page("projects")
        st.rerun()
        return
    from dataverse.services import project_service

    project = project_service.get_project(user.id, project_id)
    st.subheader(project.name)
    st.info(f"Profiling and dashboards arrive with the next milestone. Status: `{project.status}`.")
