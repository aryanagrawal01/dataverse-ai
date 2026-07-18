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
    """Project workspace: tabbed views over one dataset."""
    project_id = state.get_active_project_id()
    if project_id is None:
        state.set_nav_page("projects")
        st.rerun()
        return
    from dataverse.services import pipeline_service, project_service
    from dataverse.ui.pages_impl import dashboard, data_health

    project = project_service.get_project(user.id, project_id)
    head_l, head_r = st.columns([5, 1.3])
    with head_l:
        st.subheader(project.name)
        st.caption(
            f"{project.row_count:,} rows · {project.column_count} columns · "
            f"status `{project.status}`"
        )
    with head_r:
        st.download_button(
            "⬇ Download CSV",
            data=pipeline_service.export_csv(user.id, project_id),
            file_name=f"{project.name}-cleaned.csv",
            mime="text/csv",
            use_container_width=True,
            help="Cleaned dataset (raw if cleaning hasn't been applied yet)",
        )

    tab_health, tab_dash = st.tabs(["🩺 Data Health", "📊 Dashboard"])
    with tab_health:
        data_health.render(user, project_id)
    with tab_dash:
        dashboard.render(user, project_id)
