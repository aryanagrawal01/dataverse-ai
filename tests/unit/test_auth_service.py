import pytest

from dataverse.config import get_settings
from dataverse.services import auth_service
from dataverse.utils.errors import (
    AccountLockedError,
    EmailTakenError,
    InvalidCredentialsError,
    SessionExpiredError,
    ValidationError,
    WeakPasswordError,
)

EMAIL = "user@example.com"
PASSWORD = "sufficient9"


def test_register_returns_working_session():
    result = auth_service.register(EMAIL, PASSWORD, "Test User")
    assert result.user.email == EMAIL
    user = auth_service.current_user(result.token)
    assert user.id == result.user.id


def test_register_normalizes_email_case():
    auth_service.register("MiXeD@Example.COM", PASSWORD)
    result = auth_service.login("mixed@example.com", PASSWORD)
    assert result.user.email == "mixed@example.com"


def test_register_rejects_duplicate_email():
    auth_service.register(EMAIL, PASSWORD)
    with pytest.raises(EmailTakenError):
        auth_service.register(EMAIL, "different9pass")


def test_register_rejects_bad_email_and_weak_password():
    with pytest.raises(ValidationError):
        auth_service.register("not-an-email", PASSWORD)
    with pytest.raises(WeakPasswordError):
        auth_service.register(EMAIL, "short")


def test_login_roundtrip():
    auth_service.register(EMAIL, PASSWORD)
    result = auth_service.login(EMAIL, PASSWORD)
    assert auth_service.current_user(result.token).email == EMAIL


def test_login_wrong_password_rejected():
    auth_service.register(EMAIL, PASSWORD)
    with pytest.raises(InvalidCredentialsError):
        auth_service.login(EMAIL, "wrongpass99")


def test_login_unknown_email_gives_same_error_as_wrong_password():
    """No user enumeration: identical error either way."""
    auth_service.register(EMAIL, PASSWORD)
    with pytest.raises(InvalidCredentialsError) as unknown:
        auth_service.login("ghost@example.com", PASSWORD)
    with pytest.raises(InvalidCredentialsError) as wrong:
        auth_service.login(EMAIL, "wrongpass99")
    assert unknown.value.user_message == wrong.value.user_message


def test_lockout_after_max_failures():
    auth_service.register(EMAIL, PASSWORD)
    for _ in range(get_settings().login_max_failures):
        with pytest.raises(InvalidCredentialsError):
            auth_service.login(EMAIL, "wrongpass99")
    # Even the CORRECT password is now rejected while locked.
    with pytest.raises(AccountLockedError):
        auth_service.login(EMAIL, PASSWORD)


def test_successful_login_resets_failure_counter():
    auth_service.register(EMAIL, PASSWORD)
    for _ in range(get_settings().login_max_failures - 1):
        with pytest.raises(InvalidCredentialsError):
            auth_service.login(EMAIL, "wrongpass99")
    auth_service.login(EMAIL, PASSWORD)  # resets counter
    with pytest.raises(InvalidCredentialsError):
        auth_service.login(EMAIL, "wrongpass99")  # 1 failure, not locked
    auth_service.login(EMAIL, PASSWORD)


def test_logout_revokes_session():
    result = auth_service.register(EMAIL, PASSWORD)
    auth_service.logout(result.token)
    with pytest.raises(SessionExpiredError):
        auth_service.current_user(result.token)


def test_logout_is_idempotent():
    result = auth_service.register(EMAIL, PASSWORD)
    auth_service.logout(result.token)
    auth_service.logout(result.token)
    auth_service.logout("garbage-token")


def test_garbage_token_rejected():
    with pytest.raises(SessionExpiredError):
        auth_service.current_user("not-a-real-token")
