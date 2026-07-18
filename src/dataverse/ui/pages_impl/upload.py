"""Upload page. M1: designed placeholder; ingestion lands in M2."""

import streamlit as st

from dataverse.schemas.auth import UserDTO
from dataverse.ui.components.empty_states import hero


def render(user: UserDTO) -> None:
    st.subheader("New project")
    hero(
        badge="Coming with the next milestone",
        title="Dataset upload is almost here",
        subtitle=(
            "CSV and Excel ingestion with automatic profiling arrives in M2. "
            "The upload dropzone will live on this page."
        ),
    )
