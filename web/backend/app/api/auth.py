from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from web.backend.app.api.dependencies import current_user, optional_auth, require_csrf
from web.backend.app.database import get_db
from web.backend.app.errors import WebApiError
from web.backend.app.models import AuthSession, User
from web.backend.app.runtime_config import application_base_url, registration_enabled
from web.backend.app.schemas.auth import AuthResponse, ForgotPasswordRequest, LoginRequest, MessageResponse, RegisterRequest, ResetPasswordRequest, UserResponse
from web.backend.app.security import COOKIE_NAME, CSRF_COOKIE_NAME, same_site_cookies, secure_cookies, session_max_age
from web.backend.app.services.auth import AuthService
from web.backend.app.services.email_delivery import EmailDelivery, get_email_delivery

LOGGER = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
_attempts: dict[str, deque[float]] = defaultdict(deque)
RECOVERY_MESSAGE = "Se existir uma conta para este e-mail, as instruções de recuperação serão enviadas."


def _user(user: User) -> UserResponse:
    return UserResponse.model_validate(user, from_attributes=True)


def _set_auth_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    common = {"secure": secure_cookies(), "samesite": same_site_cookies(), "max_age": session_max_age(), "path": "/"}
    response.set_cookie(COOKIE_NAME, session_token, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE_NAME, csrf_token, httponly=False, **common)


def _rate_limit(request: Request, identity: str) -> None:
    key = f"{request.client.host if request.client else 'unknown'}:{identity.casefold().strip()}"
    now = time.monotonic()
    attempts = _attempts[key]
    while attempts and now - attempts[0] > 60:
        attempts.popleft()
    if len(attempts) >= 8:
        raise WebApiError(429, "auth_rate_limited", "Muitas tentativas. Tente novamente mais tarde.", str(uuid4()))
    attempts.append(now)


def _authenticated(response: Response, service: AuthService, user: User) -> AuthResponse:
    created = service.create_session(user)
    _set_auth_cookies(response, created.raw_token, created.raw_csrf)
    return AuthResponse(user=_user(user), csrf_token=created.raw_csrf)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    if not registration_enabled():
        raise WebApiError(403, "registration_disabled", "O cadastro público está desabilitado.", str(uuid4()))
    service = AuthService(db)
    try:
        user = service.register(payload.email, payload.password, payload.password_confirmation)
    except IntegrityError as error:
        raise WebApiError(409, "registration_unavailable", "Não foi possível concluir o cadastro.", str(uuid4())) from error
    except ValueError as error:
        raise WebApiError(422, "invalid_registration", str(error), str(uuid4())) from error
    LOGGER.info("AUTH_REGISTRATION_SUCCEEDED", extra={"user_id": user.id})
    return _authenticated(response, service, user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    _rate_limit(request, payload.email)
    service = AuthService(db)
    user = service.authenticate(payload.email, payload.password)
    if not user:
        LOGGER.warning("AUTH_LOGIN_FAILED")
        raise WebApiError(401, "invalid_credentials", "E-mail ou senha inválidos.", str(uuid4()))
    LOGGER.info("AUTH_LOGIN_SUCCEEDED", extra={"user_id": user.id})
    return _authenticated(response, service, user)


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
def logout(response: Response, auth: tuple[User, AuthSession] | None = Depends(optional_auth), db: Session = Depends(get_db)) -> None:
    if auth:
        AuthService(db).revoke_session(auth[1])
        LOGGER.info("AUTH_LOGOUT", extra={"user_id": auth[0].id})
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


@router.get("/me", response_model=AuthResponse)
def me(request: Request, user: User = Depends(current_user)) -> AuthResponse:
    return AuthResponse(user=_user(user), csrf_token=request.cookies.get(CSRF_COOKIE_NAME, ""))


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db), delivery: EmailDelivery = Depends(get_email_delivery)) -> MessageResponse:
    _rate_limit(request, payload.email)
    requested = AuthService(db).request_password_reset(payload.email)
    if requested:
        user, raw_token = requested
        delivery.send_password_reset(email=user.email, reset_url=f"{application_base_url()}/reset-password?token={raw_token}")
    LOGGER.info("AUTH_PASSWORD_RESET_REQUESTED")
    return MessageResponse(message=RECOVERY_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    try:
        completed = AuthService(db).reset_password(payload.token, payload.password, payload.password_confirmation)
    except ValueError as error:
        raise WebApiError(422, "invalid_password", str(error), str(uuid4())) from error
    if not completed:
        raise WebApiError(400, "invalid_reset_token", "O link de recuperação é inválido ou expirou.", str(uuid4()))
    LOGGER.info("AUTH_PASSWORD_RESET_COMPLETED")
    return MessageResponse(message="Senha alterada com sucesso.")
