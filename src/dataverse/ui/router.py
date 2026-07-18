"""Session-aware navigation.

M0: renders the public landing shell. Auth-gated routing arrives with M1.
"""

from dataverse.ui.errors import page_boundary
from dataverse.ui.pages_impl import landing


@page_boundary
def route() -> None:
    landing.render()
