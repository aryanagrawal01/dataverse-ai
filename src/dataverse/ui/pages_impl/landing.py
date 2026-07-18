"""Public landing shell (M0). Replaced by the auth flow in M1."""

import streamlit as st

from dataverse import __version__
from dataverse.ui.components.empty_states import feature_card, hero
from dataverse.ui.theme import brand_mark


def render() -> None:
    with st.sidebar:
        brand_mark()
        st.caption(f"v{__version__} · foundations")

    hero(
        badge="AI-powered Business Intelligence",
        title="From spreadsheet to insight in minutes",
        subtitle=(
            "Upload a CSV or Excel file and get automated cleaning, interactive "
            "dashboards, AI-written insights, forecasts, and a conversational "
            "interface to your data. No SQL. No Python."
        ),
    )

    cols = st.columns(4, gap="medium")
    features = [
        (
            "🩺",
            "Data Health",
            "Automatic profiling with a 0–100 health score and transparent, reviewable cleaning.",
        ),
        (
            "📊",
            "Instant Dashboards",
            "KPIs, trends, breakdowns, and correlations generated from your data's shape.",
        ),
        (
            "💬",
            "Chat with Data",
            "Ask questions in plain language — answers are computed, never hallucinated.",
        ),
        (
            "📈",
            "Forecasts & Reports",
            "Backtested forecasts with honest error ranges, exported as polished PDFs.",
        ),
    ]
    for col, (icon, title, text) in zip(cols, features, strict=True):
        with col:
            feature_card(icon, title, text)

    st.markdown("")
    _, center, _ = st.columns([2, 1, 2])
    with center:
        st.button(
            "Get started",
            type="primary",
            use_container_width=True,
            disabled=True,
            help="Sign-in arrives with the next milestone (M1).",
        )
