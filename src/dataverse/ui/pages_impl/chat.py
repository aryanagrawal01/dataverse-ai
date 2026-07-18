"""Chat with Data page."""

import streamlit as st

from dataverse.schemas.auth import UserDTO
from dataverse.services import chat_service
from dataverse.ui.components import charts
from dataverse.utils.errors import DataVerseError


def render(user: UserDTO, project_id: str) -> None:
    messages = chat_service.history(user.id, project_id)

    if not messages:
        st.caption("Ask anything about this dataset — answers are computed, never guessed.")
        suggestions = chat_service.suggested_questions(user.id, project_id)
        if suggestions:
            cols = st.columns(len(suggestions))
            for col, question in zip(cols, suggestions, strict=True):
                with col:
                    if st.button(
                        question, key=f"starter_{hash(question)}", use_container_width=True
                    ):
                        st.session_state["dv_pending_question"] = question
                        st.rerun()

    for msg in messages:
        # NOTE: avatar must be a real emoji or image path; "◆" crashes Streamlit.
        with st.chat_message(msg.role, avatar="🔷" if msg.role == "assistant" else None):
            st.markdown(msg.content)
            if msg.chart is not None:
                charts.render_chart(msg.chart)
            if msg.plan is not None:
                with st.expander("View query (audit trail)"):
                    st.json(msg.plan.model_dump(mode="json", exclude_defaults=True))

    pending = st.session_state.pop("dv_pending_question", None)
    typed = st.chat_input("Ask anything about your data…")
    asked: str | None = pending or typed
    if asked:
        with st.chat_message("user"):
            st.markdown(asked)
        try:
            with st.chat_message("assistant", avatar="🔷"), st.spinner("Analyzing…"):
                chat_service.ask(user.id, project_id, asked)
        except DataVerseError as exc:
            # No rerun on failure — rerunning would wipe this message.
            st.warning(exc.user_message)
        else:
            st.rerun()
