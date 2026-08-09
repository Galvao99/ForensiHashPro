from __future__ import annotations

import hmac
from uuid import uuid4

from fastapi import Depends, Request, status
from sqlalchemy.orm import Session

from web.backend.app.database import get_db
from web.backend.app.errors import WebApiError
from web.backend.app.models import User, UserRole
from web.backend.app.security import COOKIE_NAME, CSRF_COOKIE_NAME, read_session_token


def auth_error(code: str = "authentication_required") -> WebApiError:
    return WebApiError(status.HTTP_401_UNAUTHORIZED, code, "Autenticação necessária.", str(uuid4()))


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    session = read_session_token(token) if token else None
    if not session:
        return None
    user = db.get(User, session[0])
    if not user or not user.is_active or user.session_version != session[1]:
        return None
    return user


def current_user(user: User | None = Depends(optional_user)) -> User:
    if not user:
        raise auth_error()
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != UserRole.ADMIN.value:
        raise WebApiError(status.HTTP_403_FORBIDDEN, "admin_required", "Acesso não autorizado.", str(uuid4()))
    return user


def require_csrf(request: Request) -> None:
    cookie = request.cookies.get(CSRF_COOKIE_NAME, "")
    header = request.headers.get("X-CSRF-Token", "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise WebApiError(status.HTTP_403_FORBIDDEN, "csrf_failed", "A solicitação não pôde ser validada.", str(uuid4()))
