"""User and session persistence."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from dataverse.models import User, UserSession


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def by_email(self, email: str) -> User | None:
        return self._s.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()

    def by_id(self, user_id: str) -> User | None:
        return self._s.get(User, user_id)

    def create(self, email: str, password_hash: str, display_name: str | None) -> User:
        user = User(email=email.lower(), password_hash=password_hash, display_name=display_name)
        self._s.add(user)
        self._s.flush()
        return user


class SessionRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def create(self, user_id: str, expires_at: datetime) -> UserSession:
        row = UserSession(user_id=user_id, expires_at=expires_at)
        self._s.add(row)
        self._s.flush()
        return row

    def by_id(self, session_id: str) -> UserSession | None:
        return self._s.get(UserSession, session_id)

    def revoke(self, session_id: str) -> None:
        row = self.by_id(session_id)
        if row is not None:
            row.revoked = True
