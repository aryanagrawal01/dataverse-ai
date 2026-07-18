"""Cleaning review panel: per-suggestion toggles, strategy pickers, apply."""

import streamlit as st

from dataverse.schemas.auth import UserDTO
from dataverse.schemas.cleaning import CleaningPlan, CleaningResult, PlanItem
from dataverse.services import pipeline_service
from dataverse.utils.errors import DataVerseError

_STRATEGY_LABELS = {
    "median": "Fill with median",
    "mean": "Fill with mean",
    "zero": "Fill with 0",
    "mode": "Fill with most common value",
    "unknown_label": 'Fill with "Unknown"',
    "drop_rows": "Drop those rows",
    "keep": "Keep as-is",
    "cap": "Cap at 1st–99th percentile",
    "remove_rows": "Remove those rows",
}


def render(user: UserDTO, project_id: str) -> None:
    suggestions = pipeline_service.suggest_cleaning_for_project(user.id, project_id)

    if not suggestions:
        st.success("Nothing to clean — this dataset is already in great shape.")
        return

    st.markdown("##### Suggested fixes")
    st.caption(
        "Review each fix before applying. Your raw file is never modified — "
        "cleaning creates a separate cleaned version you can rebuild anytime."
    )

    plan_items: list[PlanItem] = []
    for sug in suggestions:
        row = st.container(border=True)
        with row:
            col_check, col_strategy = st.columns([3, 1.4])
            with col_check:
                accepted = st.checkbox(
                    f"**{sug.title}**",
                    value=sug.enabled_by_default,
                    key=f"clean_{sug.id}",
                    help=sug.description,
                )
                st.caption(sug.description)
            params = dict(sug.params)
            with col_strategy:
                if sug.strategy_options:
                    chosen = st.selectbox(
                        "Strategy",
                        sug.strategy_options,
                        format_func=lambda v: _STRATEGY_LABELS.get(v, v),
                        key=f"strategy_{sug.id}",
                        label_visibility="collapsed",
                    )
                    params["strategy"] = chosen
            if accepted and not (
                sug.rule == "handle_outliers" and params.get("strategy") == "keep"
            ):
                plan_items.append(PlanItem(rule=sug.rule, column=sug.column, params=params))

    st.markdown("")
    if st.button(
        f"Apply {len(plan_items)} fix{'es' if len(plan_items) != 1 else ''}",
        type="primary",
        disabled=not plan_items,
    ):
        try:
            with st.spinner("Applying cleaning plan…"):
                result = pipeline_service.apply_cleaning(
                    user.id, project_id, CleaningPlan(items=plan_items)
                )
        except DataVerseError as exc:
            st.error(exc.user_message)
            return
        st.session_state["dv_last_cleaning_result"] = result.model_dump(mode="json")
        st.rerun()


def render_result_banner() -> None:
    raw = st.session_state.pop("dv_last_cleaning_result", None)
    if raw is None:
        return
    result = CleaningResult.model_validate(raw)
    c = result.comparison
    st.success("Cleaning applied — dashboards now use the cleaned data.")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Rows", f"{c.rows_after:,}", delta=f"{c.rows_after - c.rows_before:+,}")
    m2.metric(
        "Missing cells",
        f"{c.missing_cells_after:,}",
        delta=f"{c.missing_cells_after - c.missing_cells_before:+,}",
        delta_color="inverse",
    )
    m3.metric(
        "Duplicate rows",
        f"{c.duplicate_rows_after:,}",
        delta=f"{c.duplicate_rows_after - c.duplicate_rows_before:+,}",
        delta_color="inverse",
    )
    m4.metric(
        "Health score",
        f"{c.health_after}/100",
        delta=f"{c.health_after - c.health_before:+}",
    )
    with st.expander("Cleaning log"):
        for entry in result.log:
            st.markdown(f"- {entry.detail}")
