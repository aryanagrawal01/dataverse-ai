"""Data Health page: health score, issues, column details, correlations, preview."""

import pandas as pd
import streamlit as st

from dataverse.config.constants import MAX_PREVIEW_ROWS
from dataverse.schemas.auth import UserDTO
from dataverse.schemas.profiling import DatasetProfile
from dataverse.services import pipeline_service
from dataverse.ui.components import charts
from dataverse.utils.dataframe import sample_for_display

_SEVERITY_ICON = {"high": "🔴", "medium": "🟡", "low": "🔵"}
_TYPE_ICON = {
    "numeric": "🔢",
    "categorical": "🏷️",
    "datetime": "📅",
    "text": "📝",
    "boolean": "✓",
    "id": "🔑",
}


def render(user: UserDTO, project_id: str) -> None:
    profile = pipeline_service.get_stored_profile(user.id, project_id)
    if profile is None:
        with st.spinner("Profiling this dataset…"):
            profile = pipeline_service.profile_project(user.id, project_id)

    _summary_row(profile)
    st.divider()

    left, right = st.columns([1.1, 1], gap="large")
    with left:
        _issues_panel(profile)
    with right:
        _missing_panel(profile)

    st.divider()
    _columns_table(profile)

    if profile.correlations:
        st.divider()
        st.markdown("##### Correlations")
        method = st.radio(
            "Method", ["pearson", "spearman"], horizontal=True, label_visibility="collapsed"
        )
        matrix = next(m for m in profile.correlations if m.method == method)
        charts.render_correlation_heatmap(matrix)

    st.divider()
    with st.expander(f"Data preview (first {MAX_PREVIEW_ROWS} rows)"):
        df = pipeline_service.load_dataframe(user.id, project_id)
        st.dataframe(sample_for_display(df, MAX_PREVIEW_ROWS), use_container_width=True)


def _summary_row(profile: DatasetProfile) -> None:
    score = profile.health.score
    icon = "🟢" if score >= 85 else ("🟡" if score >= 60 else "🔴")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Health score", f"{icon} {score}/100")
    c2.metric("Rows", f"{profile.row_count:,}")
    c3.metric("Columns", profile.column_count)
    c4.metric("Duplicate rows", f"{profile.duplicate_row_count:,}")
    c5.metric("Memory", f"{profile.memory_bytes / 1_048_576:.1f} MB")


def _issues_panel(profile: DatasetProfile) -> None:
    st.markdown("##### Issues found")
    issues = profile.health.issues
    if not issues:
        st.success("No data quality issues detected — this dataset looks clean!")
        return
    order = {"high": 0, "medium": 1, "low": 2}
    for issue in sorted(issues, key=lambda i: order[i.severity]):
        st.markdown(f"{_SEVERITY_ICON[issue.severity]} {issue.description}")
    st.caption("Fixes for these issues arrive on the Cleaning tab (next milestone).")


def _missing_panel(profile: DatasetProfile) -> None:
    st.markdown("##### Missing values")
    with_missing = [c for c in profile.columns if c.missing_count > 0]
    if not with_missing:
        st.success("No missing values anywhere.")
        return
    with_missing.sort(key=lambda c: c.missing_pct, reverse=True)
    charts.render_missing_bar([c.name for c in with_missing], [c.missing_pct for c in with_missing])


def _columns_table(profile: DatasetProfile) -> None:
    st.markdown("##### Columns")
    rows = []
    for c in profile.columns:
        detail = ""
        if c.stats is not None and c.stats.mean is not None:
            detail = f"μ {c.stats.mean:,.2f} · min {c.stats.min:,.2f} · max {c.stats.max:,.2f}"
        elif c.semantic_type == "datetime" and c.min_date:
            detail = f"{c.min_date[:10]} → {(c.max_date or '')[:10]}"
        elif c.semantic_type in ("categorical", "text"):
            detail = ", ".join(c.sample_values[:3])
        note = ""
        if c.suggested_type:
            note = f"stored as text — {c.parse_success_pct:.0f}% parses as {c.suggested_type}"
        elif c.is_constant:
            note = "constant"
        rows.append(
            {
                "Column": c.name,
                "Type": f"{_TYPE_ICON.get(c.semantic_type, '')} {c.semantic_type}",
                "Missing": f"{c.missing_pct:.1f}%",
                "Unique": c.unique_count,
                "Details": detail,
                "⚠": note,
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
