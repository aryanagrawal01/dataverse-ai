"""Password hashing, session-token signing, and input hygiene."""

import hmac
import re

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from dataverse.config import get_settings
from dataverse.config.constants import BCRYPT_ROUNDS, MIN_PASSWORD_LENGTH
from dataverse.utils.errors import SessionExpiredError, WeakPasswordError

_pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=BCRYPT_ROUNDS)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(password, password_hash)
    except ValueError:
        return False


def validate_password_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH or not re.search(r"\d", password):
        raise WeakPasswordError(
            f"password rejected: length={len(password)}, has_digit={bool(re.search(r'\\d', password))}"
        )


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email)) and len(email) <= 255


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="dataverse.session")


def sign_session_token(session_id: str) -> str:
    """Wrap a server-side session id in a signed, tamper-evident token."""
    return _serializer().dumps(session_id)


def unsign_session_token(token: str) -> str:
    """Return the session id, or raise SessionExpiredError on bad/expired tokens."""
    settings = get_settings()
    try:
        session_id: str = _serializer().loads(token, max_age=settings.session_ttl_minutes * 60)
    except (BadSignature, SignatureExpired) as exc:
        raise SessionExpiredError(f"token rejected: {type(exc).__name__}") from exc
    return session_id


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
