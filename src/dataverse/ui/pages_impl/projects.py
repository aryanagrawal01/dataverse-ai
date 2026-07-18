"""Projects home: card grid, rename/delete, storage usage."""

import streamlit as st

from dataverse.schemas.auth import UserDTO
from dataverse.schemas.project import ProjectSummary
from dataverse.services import project_service
from dataverse.ui import state
from dataverse.ui.components.empty_states import hero
from dataverse.utils.errors import DataVerseError

_HEALTH_COLORS = [(85, "🟢"), (60, "🟡"), (0, "🔴")]


def render(user: UserDTO) -> None:
    st.subheader("Your projects")

    projects = project_service.list_projects(user.id)

    if not projects:
        hero(
            badge="Let's get started",
            title="Upload your first dataset",
            subtitle=(
                "Drop in a CSV or Excel file and DataVerse will profile it, "
                "clean it, and build your first dashboard automatically."
            ),
        )
        _, center, _ = st.columns([2, 1, 2])
        with center:
            if st.button("＋ New project", type="primary", use_container_width=True):
                state.set_nav_page("upload")
                st.rerun()
        return

    top_l, top_r = st.columns([5, 1])
    with top_r:
        if st.button("＋ New project", type="primary", use_container_width=True):
            state.set_nav_page("upload")
            st.rerun()

    for row_start in range(0, len(projects), 3):
        cols = st.columns(3, gap="medium")
        for col, project in zip(cols, projects[row_start : row_start + 3], strict=False):
            with col:
                _project_card(user, project)

    usage = project_service.storage_usage(user.id)
    st.caption(
        f"Storage: {usage.used_bytes / 1_048_576:.0f} MB / {usage.quota_bytes / 1_048_576:.0f} MB"
    )
    st.progress(usage.used_fraction)


def _health_icon(score: int | None) -> str:
    if score is None:
        return "⚪"
    return next(icon for threshold, icon in _HEALTH_COLORS if score >= threshold)


def _project_card(user: UserDTO, project: ProjectSummary) -> None:
    with st.container(border=True):
        st.markdown(f"**{project.name}**")
        health = (
            f"{_health_icon(project.health_score)} {project.health_score}/100"
            if project.health_score is not None
            else "⚪ not profiled yet"
        )
        rows = f"{project.row_count:,} rows" if project.row_count is not None else "—"
        st.caption(f"{health} · {rows} · {project.created_at:%b %d, %Y} · `{project.status}`")

        open_col, rename_col, delete_col = st.columns([2, 1, 1])
        with open_col:
            if st.button("Open", key=f"open_{project.id}", use_container_width=True):
                state.set_active_project_id(project.id)
                state.set_nav_page("project")
                st.rerun()
        with rename_col, st.popover("✏️", use_container_width=True):
            new_name = st.text_input("New name", value=project.name, key=f"rename_{project.id}")
            if st.button("Save", key=f"rename_save_{project.id}", type="primary"):
                _try(lambda: project_service.rename_project(user.id, project.id, new_name))
        with delete_col, st.popover("🗑️", use_container_width=True):
            st.warning("This permanently removes the project and its files.")
            if st.button("Delete forever", key=f"delete_{project.id}", type="primary"):
                _try(lambda: project_service.delete_project(user.id, project.id))


def _try(action) -> None:
    try:
        action()
    except DataVerseError as exc:
        st.error(exc.user_message)
        return
    st.rerun()
