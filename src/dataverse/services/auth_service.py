"""Authentication: registration, login with lockout, session lifecycle."""

from datetime import UTC, datetime, timedelta

from dataverse.config import get_settings
from dataverse.models.base import utcnow
from dataverse.repositories.base import session_scope
from dataverse.repositories.user_repo import SessionRepository, UserRepository
from dataverse.schemas.auth import AuthResult, UserDTO
from dataverse.utils.errors import (
    AccountLockedError,
    EmailTakenError,
    InvalidCredentialsError,
    SessionExpiredError,
    ValidationError,
)
from dataverse.utils.logging import get_logger
from dataverse.utils.security import (
    hash_password,
    is_valid_email,
    sign_session_token,
    unsign_session_token,
    validate_password_strength,
    verify_password,
)

log = get_logger(__name__)

# Verifying against this constant-cost dummy hash keeps login timing uniform
# whether or not the email exists (no user enumeration via response time).
_DUMMY_HASH = hash_password("timing-equalizer-dummy")


def _as_utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; normalize for comparisons."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def register(email: str, password: str, display_name: str | None = None) -> AuthResult:
    email = email.strip().lower()
    if not is_valid_email(email):
        raise ValidationError(
            f"invalid email format: {email!r}", user_message="Please enter a valid email address."
        )
    validate_password_strength(password)

    with session_scope() as s:
        users = UserRepository(s)
        if users.by_email(email) is not None:
            raise EmailTakenError(f"email already registered: {email}")
        user = users.create(email, hash_password(password), display_name)
        token = _open_session(s, user.id)
        user.last_login_at = utcnow()
        result = AuthResult(user=UserDTO.model_validate(user), token=token)

    log.info("auth.registered", user_id=result.user.id)
    return result


def login(email: str, password: str) -> AuthResult:
    email = email.strip().lower()
    settings = get_settings()

    with session_scope() as s:
        users = UserRepository(s)
        user = users.by_email(email)

        if user is None or not user.is_active:
            verify_password(password, _DUMMY_HASH)  # uniform timing
            log.info("auth.login_failed", reason="unknown_or_inactive")
            raise InvalidCredentialsError(f"login failed for {email}")

        locked_until = _as_utc(user.locked_until)
        if locked_until is not None and locked_until > utcnow():
            log.warning("auth.login_rejected_locked", user_id=user.id)
            raise AccountLockedError(f"account locked until {locked_until.isoformat()}")

        if not verify_password(password, user.password_hash):
            user.failed_logins += 1
            if user.failed_logins >= settings.login_max_failures:
                user.locked_until = utcnow() + timedelta(minutes=settings.login_lockout_minutes)
                user.failed_logins = 0
                log.warning("auth.lockout_triggered", user_id=user.id)
            else:
                log.info("auth.login_failed", user_id=user.id, reason="bad_password")
            # The raise below triggers session_scope's rollback — persist the
            # failure counter/lockout first or brute-force tracking is lost.
            s.commit()
            raise InvalidCredentialsError(f"bad password for {email}")

        user.failed_logins = 0
        user.locked_until = None
        user.last_login_at = utcnow()
        token = _open_session(s, user.id)
        result = AuthResult(user=UserDTO.model_validate(user), token=token)

    log.info("auth.login_succeeded", user_id=result.user.id)
    return result


def logout(token: str) -> None:
    try:
        session_id = unsign_session_token(token)
    except SessionExpiredError:
        return  # already dead — logout is idempotent
    with session_scope() as s:
        SessionRepository(s).revoke(session_id)
    log.info("auth.logout")


def current_user(token: str) -> UserDTO:
    """Resolve a session token to its user, or raise SessionExpiredError."""
    session_id = unsign_session_token(token)  # signature + TTL check
    with session_scope() as s:
        row = SessionRepository(s).by_id(session_id)
        if row is None or row.revoked:
            raise SessionExpiredError("session revoked or unknown")
        expires_at = _as_utc(row.expires_at)
        if expires_at is not None and expires_at < utcnow():
            raise SessionExpiredError("session expired server-side")
        user = UserRepository(s).by_id(row.user_id)
        if user is None or not user.is_active:
            raise SessionExpiredError("user gone or deactivated")
        return UserDTO.model_validate(user)


def _open_session(s, user_id: str) -> str:  # type: ignore[no-untyped-def]
    settings = get_settings()
    expires = utcnow() + timedelta(minutes=settings.session_ttl_minutes)
    row = SessionRepository(s).create(user_id, expires)
    return sign_session_token(row.id)
