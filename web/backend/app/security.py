from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from web.backend.app.runtime_config import cookie_samesite, cookie_secure, deployed_environment


COOKIE_NAME = "forensihash_session"
CSRF_COOKIE_NAME = "forensihash_csrf"
SESSION_MAX_AGE = 8 * 60 * 60
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


def _secret() -> bytes:
    value = os.environ.get("FORENSIHASH_SESSION_SECRET", "")
    if len(value) < 32:
        if deployed_environment():
            raise RuntimeError("FORENSIHASH_SESSION_SECRET deve possuir ao menos 32 caracteres.")
        value = "development-only-change-before-production"
    return value.encode("utf-8")


def create_session_token(user_id: str, session_version: int) -> str:
    payload = {"sub": user_id, "sv": session_version, "exp": int(time.time()) + SESSION_MAX_AGE}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
    signature = hmac.new(_secret(), encoded, hashlib.sha256).digest()
    return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def read_session_token(token: str) -> tuple[str, int] | None:
    try:
        encoded_text, signature_text = token.split(".", 1)
        encoded = encoded_text.encode()
        expected = hmac.new(_secret(), encoded, hashlib.sha256).digest()
        signature = base64.urlsafe_b64decode(signature_text + "=" * (-len(signature_text) % 4))
        if not hmac.compare_digest(expected, signature):
            return None
        payload = json.loads(base64.urlsafe_b64decode(encoded_text + "=" * (-len(encoded_text) % 4)))
        if int(payload["exp"]) < int(time.time()):
            return None
        return str(payload["sub"]), int(payload["sv"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def secure_cookies() -> bool:
    return cookie_secure()


def same_site_cookies() -> str:
    return cookie_samesite()
