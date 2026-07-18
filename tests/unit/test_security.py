import pytest

from dataverse.utils import security
from dataverse.utils.errors import SessionExpiredError, WeakPasswordError


def test_password_hash_roundtrip():
    h = security.hash_password("correct horse 9")
    assert h != "correct horse 9"
    assert security.verify_password("correct horse 9", h)
    assert not security.verify_password("wrong", h)


def test_verify_handles_garbage_hash():
    assert not security.verify_password("x", "not-a-bcrypt-hash")


@pytest.mark.parametrize("bad", ["short1", "nodigitshere", "1234567"])
def test_weak_passwords_rejected(bad):
    with pytest.raises(WeakPasswordError):
        security.validate_password_strength(bad)


def test_strong_password_accepted():
    security.validate_password_strength("sufficient9")


@pytest.mark.parametrize(
    ("email", "ok"),
    [
        ("a@b.co", True),
        ("user.name+tag@example.org", True),
        ("no-at-sign", False),
        ("two@@x.com", False),
        ("spaces in@x.com", False),
        ("", False),
    ],
)
def test_email_validation(email, ok):
    assert security.is_valid_email(email) is ok


def test_session_token_roundtrip():
    token = security.sign_session_token("session-123")
    assert security.unsign_session_token(token) == "session-123"


def test_tampered_token_rejected():
    token = security.sign_session_token("session-123")
    with pytest.raises(SessionExpiredError):
        security.unsign_session_token(token + "tamper")
