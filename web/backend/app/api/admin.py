from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from web.backend.app.api.dependencies import admin_user, require_csrf
from web.backend.app.database import get_db
from web.backend.app.errors import WebApiError
from web.backend.app.models import User, UserRole, WebAnalysisProfile
from web.backend.app.schemas.auth import AdminUserPatchRequest, UserResponse


router = APIRouter(prefix="/api/v1/admin/users", tags=["admin"], dependencies=[Depends(admin_user)])


@router.get("", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db)) -> list[UserResponse]:
    return [UserResponse.model_validate(user, from_attributes=True) for user in db.scalars(select(User).order_by(User.created_at.desc()))]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, db: Session = Depends(get_db)) -> UserResponse:
    user = db.get(User, user_id)
    if not user:
        raise WebApiError(404, "user_not_found", "Usuário não encontrado.", str(uuid4()))
    return UserResponse.model_validate(user, from_attributes=True)


@router.patch("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_csrf)])
def update_user(user_id: str, payload: AdminUserPatchRequest, db: Session = Depends(get_db)) -> UserResponse:
    user = db.get(User, user_id)
    if not user:
        raise WebApiError(404, "user_not_found", "Usuário não encontrado.", str(uuid4()))
    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.role is not None:
        try:
            user.role = UserRole(payload.role).value
        except ValueError as error:
            raise WebApiError(422, "invalid_role", "Papel inválido.", str(uuid4())) from error
    if payload.analysis_profile is not None:
        try:
            user.analysis_profile = WebAnalysisProfile(payload.analysis_profile).value
        except ValueError as error:
            raise WebApiError(422, "invalid_analysis_profile", "Perfil de análise inválido.", str(uuid4())) from error
    if payload.is_active is not None:
        user.is_active = payload.is_active
        if not payload.is_active:
            user.session_version += 1
    db.commit()
    return UserResponse.model_validate(user, from_attributes=True)
