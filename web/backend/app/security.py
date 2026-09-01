from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from web.backend.app.runtime_config import cookie_samesite, cookie_secure, session_lifetime_seconds


COOKIE_NAME = "forensihash_session"
CSRF_COOKIE_NAME = "forensihash_csrf"
_PASSWORD_HASHER = PasswordHasher()


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def validate_password(password: str) -> None:
    if len(password) < 12 or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise ValueError("A senha deve possuir ao menos 12 caracteres, letras e números.")


def normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if len(normalized) > 320 or normalized.count("@") != 1:
        raise ValueError("E-mail inválido.")
    local, domain = normalized.split("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("E-mail inválido.")
    return normalized


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def secure_cookies() -> bool:
    return cookie_secure()


def same_site_cookies() -> str:
    return cookie_samesite()


def session_max_age() -> int:
    return session_lifetime_seconds()
