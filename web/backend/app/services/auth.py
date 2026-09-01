from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from web.backend.app.models import AuthSession, PasswordResetToken, User, UserPrivacyPreferences, UserStatus
from web.backend.app.runtime_config import reset_token_lifetime_seconds, session_lifetime_seconds
from web.backend.app.security import hash_password, new_opaque_token, normalize_email, token_digest, validate_password, verify_password


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class CreatedSession:
    raw_token: str
    raw_csrf: str
    record: AuthSession


class AuthService:
    def __init__(self, database: Session) -> None:
        self.database = database

    def register(self, email: str, password: str, confirmation: str | None) -> User:
        normalized = normalize_email(email)
        validate_password(password)
        if confirmation is not None and password != confirmation:
            raise ValueError("As senhas não coincidem.")
        user = User(email=normalized, password_hash=hash_password(password), status=UserStatus.ACTIVE.value)
        # Required only while legacy analysis routes remain available.
        user.privacy = UserPrivacyPreferences()
        self.database.add(user)
        try:
            self.database.commit()
        except IntegrityError:
            self.database.rollback()
            raise
        return user

    def authenticate(self, email: str, password: str) -> User | None:
        try:
            normalized = normalize_email(email)
        except ValueError:
            normalized = "invalid"
        user = self.database.scalar(select(User).where(User.email == normalized))
        if not user or user.status != UserStatus.ACTIVE.value or not user.is_active:
            return None
        if not verify_password(user.password_hash, password):
            return None
        user.last_login_at = utcnow()
        self.database.commit()
        return user

    def create_session(self, user: User) -> CreatedSession:
        raw_token, raw_csrf = new_opaque_token(), new_opaque_token()
        record = AuthSession(
            user_id=user.id,
            token_digest=token_digest(raw_token),
            csrf_digest=token_digest(raw_csrf),
            expires_at=utcnow() + timedelta(seconds=session_lifetime_seconds()),
        )
        self.database.add(record)
        self.database.commit()
        return CreatedSession(raw_token, raw_csrf, record)

    def resolve_session(self, raw_token: str) -> tuple[User, AuthSession] | None:
        record = self.database.scalar(select(AuthSession).where(AuthSession.token_digest == token_digest(raw_token)))
        now = utcnow()
        if not record or record.revoked_at is not None or _as_utc(record.expires_at) <= now:
            return None
        user = self.database.get(User, record.user_id)
        if not user or not user.is_active or user.status != UserStatus.ACTIVE.value:
            return None
        return user, record

    def revoke_session(self, record: AuthSession) -> None:
        record.revoked_at = utcnow()
        self.database.commit()

    def request_password_reset(self, email: str) -> tuple[User, str] | None:
        try:
            normalized = normalize_email(email)
        except ValueError:
            return None
        user = self.database.scalar(select(User).where(User.email == normalized))
        if not user or user.status == UserStatus.DISABLED.value:
            return None
        now = utcnow()
        self.database.execute(
            update(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).values(used_at=now)
        )
        raw_token = new_opaque_token()
        self.database.add(PasswordResetToken(
            user_id=user.id,
            token_digest=token_digest(raw_token),
            expires_at=now + timedelta(seconds=reset_token_lifetime_seconds()),
        ))
        self.database.commit()
        return user, raw_token

    def reset_password(self, raw_token: str, password: str, confirmation: str) -> bool:
        validate_password(password)
        if password != confirmation:
            raise ValueError("As senhas não coincidem.")
        record = self.database.scalar(select(PasswordResetToken).where(PasswordResetToken.token_digest == token_digest(raw_token)))
        now = utcnow()
        if not record or record.used_at is not None or _as_utc(record.expires_at) <= now:
            return False
        user = self.database.get(User, record.user_id)
        if not user:
            return False
        user.password_hash = hash_password(password)
        user.session_version += 1
        record.used_at = now
        self.database.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=now))
        self.database.commit()
        return True


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
