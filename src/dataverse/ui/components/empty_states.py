"""Designed empty/hero states — no page ever renders blank."""

import streamlit as st


def hero(badge: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="dv-hero">
            <span class="dv-hero-badge">{badge}</span>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def feature_card(icon: str, title: str, text: str) -> None:
    st.markdown(
        f"""
        <div class="dv-feature">
            <span class="dv-feature-icon">{icon}</span>
            <h4>{title}</h4>
            <p>{text}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
