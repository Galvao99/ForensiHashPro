from __future__ import annotations

import hmac
from uuid import uuid4

from fastapi import Depends, Request, status
from sqlalchemy.orm import Session

from web.backend.app.database import get_db
from web.backend.app.errors import WebApiError
from web.backend.app.models import AuthSession, User, UserRole
from web.backend.app.security import COOKIE_NAME, CSRF_COOKIE_NAME, token_digest
from web.backend.app.services.auth import AuthService


def auth_error(code: str = "authentication_required") -> WebApiError:
    return WebApiError(status.HTTP_401_UNAUTHORIZED, code, "Autenticação necessária.", str(uuid4()))


def optional_auth(request: Request, db: Session = Depends(get_db)) -> tuple[User, AuthSession] | None:
    token = request.cookies.get(COOKIE_NAME)
    return AuthService(db).resolve_session(token) if token else None


def optional_user(auth: tuple[User, AuthSession] | None = Depends(optional_auth)) -> User | None:
    return auth[0] if auth else None


def current_user(user: User | None = Depends(optional_user)) -> User:
    if not user:
        raise auth_error()
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != UserRole.ADMIN.value:
        raise WebApiError(status.HTTP_403_FORBIDDEN, "admin_required", "Acesso não autorizado.", str(uuid4()))
    return user


def require_csrf(request: Request, auth: tuple[User, AuthSession] | None = Depends(optional_auth)) -> None:
    cookie = request.cookies.get(CSRF_COOKIE_NAME, "")
    header = request.headers.get("X-CSRF-Token", "")
    if not auth or not cookie or not header or not hmac.compare_digest(cookie, header) or not hmac.compare_digest(auth[1].csrf_digest, token_digest(header)):
        raise WebApiError(status.HTTP_403_FORBIDDEN, "csrf_failed", "A solicitação não pôde ser validada.", str(uuid4()))
