"""Auto-generated interactive dashboard page."""

from datetime import date

import streamlit as st

from dataverse.schemas.auth import UserDTO
from dataverse.schemas.dashboard import DashboardFilters, DashboardSpec
from dataverse.services import dashboard_service
from dataverse.ui.components import charts


def render(user: UserDTO, project_id: str) -> None:
    base = dashboard_service.build(user.id, project_id)
    filters = _filter_bar(base)
    spec = (
        dashboard_service.build(user.id, project_id, filters) if _filters_active(filters) else base
    )

    if spec.dataset_kind == "raw":
        st.info("📎 Built on raw data — apply cleaning on the Data Health tab for best results.")

    _kpi_row(spec)
    st.markdown("")
    _chart_grid(spec)


def _filters_active(filters: DashboardFilters | None) -> bool:
    return filters is not None and bool(filters.date_from or filters.date_to or filters.categories)


def _filter_bar(spec: DashboardSpec) -> DashboardFilters | None:
    opts = spec.filter_options
    if opts.date_column is None and opts.category_column is None:
        return None
    filters = DashboardFilters()
    cols = st.columns([1.4, 1.4, 4])
    if opts.date_column and opts.date_min and opts.date_max:
        lo, hi = date.fromisoformat(opts.date_min), date.fromisoformat(opts.date_max)
        with cols[0]:
            picked = st.date_input(
                f"📅 {opts.date_column}",
                value=(lo, hi),
                min_value=lo,
                max_value=hi,
                key="dash_dates",
            )
        if isinstance(picked, tuple) and len(picked) == 2:
            start, end = picked
            if (start, end) != (lo, hi):
                filters.date_from = str(start)
                filters.date_to = str(end)
    if opts.category_column and opts.category_values:
        with cols[1]:
            chosen = st.multiselect(
                f"🏷️ {opts.category_column}", opts.category_values, key="dash_cats"
            )
        filters.categories = chosen
    return filters


def _kpi_row(spec: DashboardSpec) -> None:
    if not spec.kpis:
        return
    cols = st.columns(len(spec.kpis))
    for col, kpi in zip(cols, spec.kpis, strict=True):
        # st.metric colors negative deltas red automatically ("normal").
        col.metric(kpi.label, kpi.value, delta=kpi.delta, delta_color="normal")


def _chart_grid(spec: DashboardSpec) -> None:
    if not spec.charts:
        st.info(
            "Not enough structure to build charts from this dataset — it needs "
            "at least one numeric column."
        )
        return
    # Full-width for heatmaps/lines; two-up grid for the rest.
    wide_kinds = {"heatmap"}
    queue = list(spec.charts)
    while queue:
        spec_item = queue.pop(0)
        if spec_item.kind in wide_kinds:
            with st.container(border=True):
                charts.render_chart(spec_item)
            continue
        pair = [spec_item]
        if queue and queue[0].kind not in wide_kinds:
            pair.append(queue.pop(0))
        cols = st.columns(len(pair), gap="medium")
        for col, item in zip(cols, pair, strict=True):
            with col, st.container(border=True):
                charts.render_chart(item)
