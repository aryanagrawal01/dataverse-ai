"""DataVerse AI — Streamlit entrypoint.

Thin by design: page config, logging bootstrap, and routing only.
All page bodies live in src/dataverse/ui/pages_impl/.
"""

import streamlit as st

st.set_page_config(
    page_title="DataVerse AI",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dataverse.config import get_settings  # noqa: E402
from dataverse.ui.router import route  # noqa: E402
from dataverse.ui.theme import inject_theme  # noqa: E402
from dataverse.utils.logging import configure_logging  # noqa: E402


def main() -> None:
    configure_logging()
    get_settings().validate_for_environment()
    inject_theme()
    route()


main()
