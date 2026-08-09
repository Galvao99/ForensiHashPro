from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from web.backend.app.api.dependencies import current_user, require_csrf
from web.backend.app.database import get_db
from web.backend.app.errors import WebApiError
from web.backend.app.models import Consent, ConsentType, RetentionMode, User, UserPrivacyPreferences
from web.backend.app.schemas.auth import AuthResponse, LoginRequest, PrivacyPatchRequest, PrivacyResponse, RegisterRequest, UserPatchRequest, UserResponse
from web.backend.app.security import COOKIE_NAME, CSRF_COOKIE_NAME, SESSION_MAX_AGE, create_session_token, hash_password, new_csrf_token, normalize_email, secure_cookies, validate_password, verify_password


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
TERMS_VERSION = "2026-08"
PRIVACY_VERSION = "2026-08"
_attempts: dict[str, deque[float]] = defaultdict(deque)


def _user(user: User) -> UserResponse:
    return UserResponse.model_validate(user, from_attributes=True)


def _privacy(preferences: UserPrivacyPreferences) -> PrivacyResponse:
    return PrivacyResponse.model_validate(preferences, from_attributes=True)


def _set_auth_cookies(response: Response, user: User) -> str:
    csrf = new_csrf_token()
    common = {"secure": secure_cookies(), "samesite": "lax", "max_age": SESSION_MAX_AGE, "path": "/"}
    response.set_cookie(COOKIE_NAME, create_session_token(user.id, user.session_version), httponly=True, **common)
    response.set_cookie(CSRF_COOKIE_NAME, csrf, httponly=False, **common)
    return csrf


def _rate_limit(request: Request, email: str) -> None:
    key = f"{request.client.host if request.client else 'unknown'}:{email}"
    now = time.monotonic()
    attempts = _attempts[key]
    while attempts and now - attempts[0] > 60:
        attempts.popleft()
    if len(attempts) >= 8:
        raise WebApiError(status.HTTP_429_TOO_MANY_REQUESTS, "login_rate_limited", "Muitas tentativas. Tente novamente mais tarde.", str(uuid4()))
    attempts.append(now)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    if not payload.accept_terms or not payload.accept_privacy:
        raise WebApiError(422, "consent_required", "É necessário aceitar os termos e a política de privacidade.", str(uuid4()))
    try:
        email = normalize_email(payload.email)
        validate_password(payload.password)
    except ValueError as error:
        raise WebApiError(422, "invalid_registration", str(error), str(uuid4())) from error
    user = User(name=payload.name.strip(), email=email, password_hash=hash_password(payload.password))
    user.privacy = UserPrivacyPreferences()
    db.add(user)
    try:
        db.flush()
        db.add_all([
            Consent(user_id=user.id, document_type=ConsentType.TERMS_OF_USE.value, document_version=TERMS_VERSION),
            Consent(user_id=user.id, document_type=ConsentType.PRIVACY_POLICY.value, document_version=PRIVACY_VERSION),
        ])
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise WebApiError(409, "registration_unavailable", "Não foi possível concluir o cadastro.", str(uuid4())) from error
    return AuthResponse(user=_user(user), privacy=_privacy(user.privacy), csrf_token=_set_auth_cookies(response, user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        email = normalize_email(payload.email)
    except ValueError:
        email = "invalid"
    _rate_limit(request, email)
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or not verify_password(user.password_hash, payload.password):
        raise WebApiError(401, "invalid_credentials", "E-mail ou senha inválidos.", str(uuid4()))
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return AuthResponse(user=_user(user), privacy=_privacy(user.privacy), csrf_token=_set_auth_cookies(response, user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def logout(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    user.session_version += 1
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


@router.get("/me", response_model=AuthResponse)
def me(response: Response, user: User = Depends(current_user)) -> AuthResponse:
    csrf = new_csrf_token()
    response.set_cookie(CSRF_COOKIE_NAME, csrf, httponly=False, secure=secure_cookies(), samesite="lax", max_age=SESSION_MAX_AGE, path="/")
    return AuthResponse(user=_user(user), privacy=_privacy(user.privacy), csrf_token=csrf)


@router.patch("/me", response_model=UserResponse, dependencies=[Depends(require_csrf)])
def update_me(payload: UserPatchRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> UserResponse:
    if payload.name is not None:
        user.name = payload.name.strip()
    db.commit()
    return _user(user)


@router.patch("/privacy", response_model=PrivacyResponse, dependencies=[Depends(require_csrf)])
def update_privacy(payload: PrivacyPatchRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> PrivacyResponse:
    try:
        mode = RetentionMode(payload.retention_mode)
    except ValueError as error:
        raise WebApiError(422, "invalid_retention", "Modo de retenção inválido.", str(uuid4())) from error
    if mode is RetentionMode.FILE_AND_RESULT:
        raise WebApiError(422, "file_retention_unavailable", "A retenção de arquivos ainda não está disponível.", str(uuid4()))
    user.privacy.retention_mode = mode.value
    user.privacy.retain_analysis_results = mode is RetentionMode.RESULT_ONLY
    user.privacy.retain_original_files = False
    user.privacy.allow_external_services = payload.allow_external_services
    db.commit()
    return _privacy(user.privacy)
