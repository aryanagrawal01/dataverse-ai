"""Upload page: dropzone, sheet picker, sample dataset, parse → profile → open."""

from pathlib import Path

import streamlit as st

from dataverse.config import get_settings
from dataverse.schemas.auth import UserDTO
from dataverse.services import ingestion_service, pipeline_service
from dataverse.ui import state
from dataverse.utils.errors import DataVerseError

_SAMPLES_DIR = Path(__file__).resolve().parents[4] / "sample_data"


def _samples_dir() -> Path:
    # repo_root/sample_data — resolve relative to package location or CWD fallback
    for candidate in (_SAMPLES_DIR, Path("sample_data")):
        if candidate.is_dir():
            return candidate
    return Path("sample_data")


def render(user: UserDTO) -> None:
    settings = get_settings()
    st.subheader("New project")
    st.caption(
        f"Upload a CSV or Excel file (max {settings.max_upload_mb} MB). "
        "We'll profile it and flag data quality issues automatically."
    )

    uploaded = st.file_uploader(
        "Drag and drop, or browse",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=False,
        label_visibility="collapsed",
    )

    sheet: str | None = None
    if uploaded is not None and uploaded.name.lower().endswith((".xlsx", ".xls")):
        ext = "." + uploaded.name.rsplit(".", 1)[-1].lower()
        try:
            sheets = ingestion_service.excel_sheet_names(uploaded.getvalue(), ext)
        except DataVerseError as exc:
            st.error(exc.user_message)
            return
        if len(sheets) > 1:
            sheet = st.selectbox("This workbook has multiple sheets — pick one:", sheets)

    col_run, col_sample = st.columns([1, 1])
    with col_run:
        start = st.button(
            "Create project",
            type="primary",
            use_container_width=True,
            disabled=uploaded is None,
        )
    with col_sample:
        use_sample = st.button(
            "✨ Try a sample dataset", use_container_width=True, help="Demo retail sales data"
        )

    if start and uploaded is not None:
        _ingest(user, uploaded.name, uploaded.getvalue(), sheet)
    elif use_sample:
        sample = _samples_dir() / "retail_sales_demo.csv"
        if not sample.is_file():
            st.error("Sample dataset is missing from this installation.")
            return
        _ingest(user, sample.name, sample.read_bytes(), None)


def _ingest(user: UserDTO, filename: str, data: bytes, sheet: str | None) -> None:
    try:
        with st.status("Creating your project…", expanded=True) as status:
            st.write("Validating and parsing the file…")
            project = ingestion_service.create_project_from_upload(user.id, filename, data, sheet)
            st.write(f"Parsed **{project.row_count:,} rows** × {project.column_count} columns.")
            st.write("Profiling data quality…")
            profile = pipeline_service.profile_project(user.id, project.id)
            st.write(f"Health score: **{profile.health.score}/100**")
            status.update(label="Project ready!", state="complete")
    except DataVerseError as exc:
        st.error(exc.user_message)
        return

    state.set_active_project_id(project.id)
    state.set_nav_page("project")
    st.rerun()
