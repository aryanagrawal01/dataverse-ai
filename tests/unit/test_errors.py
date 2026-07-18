import pytest

from dataverse.utils import errors


def test_every_error_has_user_safe_message():
    """No error class may leak internals through its default user message."""
    for name in dir(errors):
        obj = getattr(errors, name)
        if isinstance(obj, type) and issubclass(obj, errors.DataVerseError):
            exc = obj("internal: stack details xyz")
            assert exc.user_message == obj.default_user_message
            assert "internal" not in exc.user_message
            assert exc.error_code


def test_context_is_captured():
    exc = errors.ParseError("bad delimiter", filename="a.csv", encoding="utf-8")
    assert exc.context == {"filename": "a.csv", "encoding": "utf-8"}


def test_hierarchy():
    assert issubclass(errors.InvalidCredentialsError, errors.AuthError)
    assert issubclass(errors.ParseError, errors.IngestionError)
    assert issubclass(errors.UnanswerableError, errors.ChatError)
    with pytest.raises(errors.DataVerseError):
        raise errors.FileTooLargeError("too big")
