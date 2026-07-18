"""AI Insights page: executive summary + insight cards + regenerate."""

import streamlit as st

from dataverse.config import get_settings
from dataverse.schemas.auth import UserDTO
from dataverse.services import insight_service
from dataverse.utils.errors import DataVerseError

_KIND_ICON = {
    "executive_summary": "📋",
    "trend": "📈",
    "segment": "🧩",
    "anomaly": "⚠️",
    "recommendation": "🎯",
}


def render(user: UserDTO, project_id: str) -> None:
    top_l, top_r = st.columns([5, 1.2])
    with top_r:
        regenerate = st.button("↻ Regenerate", use_container_width=True)

    try:
        with st.spinner("Analyzing your data…"):
            insight_set = insight_service.generate(user.id, project_id, force=regenerate)
    except DataVerseError as exc:
        st.error(exc.user_message)
        return

    if insight_set.model_used == "template" and not get_settings().llm_configured:
        st.info(
            "🔌 Showing rule-based insights. Add an OPENAI_API_KEY to get "
            "AI-written narrative insights — all numbers stay computed either way."
        )

    summary = next((i for i in insight_set.items if i.kind == "executive_summary"), None)
    others = [i for i in insight_set.items if i.kind != "executive_summary"]

    if summary is not None:
        with st.container(border=True):
            st.markdown(f"##### {_KIND_ICON['executive_summary']} {summary.title}")
            st.markdown(summary.content)

    for row_start in range(0, len(others), 2):
        cols = st.columns(2, gap="medium")
        for col, item in zip(cols, others[row_start : row_start + 2], strict=False):
            with col, st.container(border=True):
                st.markdown(f"**{_KIND_ICON.get(item.kind, '💡')} {item.title}**")
                st.markdown(item.content)

    st.caption(
        f"Every figure above was computed directly from your data "
        f"(narrative: {insight_set.model_used})."
    )
