"""Top-level UI error boundary.

Wrap page bodies so users see styled messages, never tracebacks.
"""

from collections.abc import Callable
from functools import wraps

import streamlit as st

from dataverse.utils.errors import DataVerseError
from dataverse.utils.logging import get_logger, new_request_id

log = get_logger(__name__)


def page_boundary[**P](page_fn: Callable[P, None]) -> Callable[P, None]:
    @wraps(page_fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            page_fn(*args, **kwargs)
        except DataVerseError as exc:
            log.warning("page.expected_error", error_code=exc.error_code, detail=exc.message)
            st.error(exc.user_message)
        except Exception:
            request_id = new_request_id()
            log.exception("page.unexpected_error", request_id=request_id)
            st.error(
                "Something went wrong on our side. Please try again — "
                f"if it keeps happening, mention reference `{request_id}`."
            )

    return wrapper
