"""Structured logging setup (structlog).

Dev: pretty console output. Prod/staging: JSON lines to stdout.
Context (request_id, user_id, project_id) is bound via contextvars so every
nested log line carries it automatically.
"""

import logging
import sys
import uuid

import structlog

from dataverse.config import get_settings

_configured = False


def configure_logging() -> None:
    """Idempotent global logging configuration. Call once at startup."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    level = getattr(logging, settings.log_level)

    logging.basicConfig(stream=sys.stdout, level=level, format="%(message)s")
    # Quiet noisy third-party loggers
    for noisy in ("urllib3", "botocore", "openai", "httpx", "watchdog"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.typing.Processor
    if settings.environment == "dev":
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    configure_logging()
    return structlog.get_logger(name)


def new_request_id() -> str:
    """Short request id shown to users on unexpected errors for support reference."""
    return uuid.uuid4().hex[:12]


def bind_context(**kwargs: str) -> None:
    """Bind identifiers (request_id, user_id, project_id) onto all subsequent logs."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()
