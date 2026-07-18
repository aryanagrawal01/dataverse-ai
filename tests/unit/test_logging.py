from dataverse.utils.logging import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    new_request_id,
)


def test_configure_is_idempotent():
    configure_logging()
    configure_logging()
    log = get_logger("test")
    log.info("hello", key="value")


def test_request_ids_are_short_and_unique():
    a, b = new_request_id(), new_request_id()
    assert a != b
    assert len(a) == 12


def test_context_binding_does_not_raise():
    bind_context(request_id="abc", user_id="u1")
    get_logger("test").info("with context")
    clear_context()
