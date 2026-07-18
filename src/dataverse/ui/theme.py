"""Design tokens and global CSS injection for the premium look.

All custom styling lives here — pages/components never embed raw CSS.
"""

import streamlit as st

# Design tokens
PRIMARY = "#4F46E5"  # indigo
PRIMARY_DARK = "#4338CA"
INK = "#1A1D27"
INK_SOFT = "#5A6072"
SURFACE = "#FFFFFF"
CANVAS = "#FAFAFC"
BORDER = "#E7E8EF"
SUCCESS = "#16A34A"
WARNING = "#D97706"
DANGER = "#DC2626"

_GLOBAL_CSS = f"""
<style>
/* --- Typography & base --- */
html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif;
}}
h1, h2, h3 {{ letter-spacing: -0.02em; color: {INK}; }}

/* --- Hide Streamlit chrome for a product feel --- */
#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}

/* --- Sidebar --- */
section[data-testid="stSidebar"] {{
    background: {SURFACE};
    border-right: 1px solid {BORDER};
}}
section[data-testid="stSidebar"] .stButton button {{
    width: 100%;
    justify-content: flex-start;
    border: none;
    background: transparent;
    color: {INK_SOFT};
    font-weight: 500;
}}
section[data-testid="stSidebar"] .stButton button:hover {{
    background: {CANVAS};
    color: {PRIMARY};
}}

/* --- Cards --- */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {SURFACE};
    border-radius: 12px;
}}

/* --- Primary buttons --- */
.stButton button[kind="primary"] {{
    background: {PRIMARY};
    border-radius: 8px;
    font-weight: 600;
    border: none;
}}
.stButton button[kind="primary"]:hover {{ background: {PRIMARY_DARK}; }}

/* --- Metric (KPI) cards --- */
div[data-testid="stMetric"] {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}}
div[data-testid="stMetricLabel"] {{ color: {INK_SOFT}; font-weight: 500; }}

/* --- Brand mark --- */
.dv-brand {{
    display: flex; align-items: center; gap: 10px;
    font-size: 1.15rem; font-weight: 700; color: {INK};
    padding: 4px 0 14px 0;
}}
.dv-brand .dv-logo {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 30px; height: 30px; border-radius: 8px;
    background: linear-gradient(135deg, {PRIMARY} 0%, #7C3AED 100%);
    color: white; font-size: 0.95rem;
}}

/* --- Hero (empty states / landing) --- */
.dv-hero {{
    text-align: center;
    padding: 56px 24px 40px 24px;
}}
.dv-hero .dv-hero-badge {{
    display: inline-block;
    background: #EEF2FF; color: {PRIMARY};
    border-radius: 999px; padding: 6px 14px;
    font-size: 0.8rem; font-weight: 600;
    margin-bottom: 18px;
}}
.dv-hero h1 {{ font-size: 2.3rem; margin: 0 0 12px 0; }}
.dv-hero p {{ color: {INK_SOFT}; font-size: 1.05rem; max-width: 560px; margin: 0 auto; }}

/* --- Feature card grid --- */
.dv-feature {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 20px;
    height: 100%;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}}
.dv-feature .dv-feature-icon {{ font-size: 1.4rem; }}
.dv-feature h4 {{ margin: 10px 0 6px 0; color: {INK}; }}
.dv-feature p {{ color: {INK_SOFT}; font-size: 0.88rem; margin: 0; }}
</style>
"""


def inject_theme() -> None:
    """Apply global CSS. Call once per page render, right after set_page_config."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


def brand_mark() -> None:
    st.markdown(
        '<div class="dv-brand"><span class="dv-logo">◆</span> DataVerse AI</div>',
        unsafe_allow_html=True,
    )
