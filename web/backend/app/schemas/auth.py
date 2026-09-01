from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str
    password_confirmation: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    status: str
    email_verified: bool
    created_at: datetime
    last_login_at: datetime | None


class UserPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)


class AdminUserPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    role: str | None = None
    analysis_profile: str | None = None
    is_active: bool | None = None


class PrivacyResponse(BaseModel):
    retention_mode: str
    retain_analysis_results: bool
    retain_original_files: bool
    allow_external_services: bool
    updated_at: datetime


class PrivacyPatchRequest(BaseModel):
    retention_mode: str
    allow_external_services: bool = False


class AuthResponse(BaseModel):
    user: UserResponse
    csrf_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str
    password_confirmation: str


class MessageResponse(BaseModel):
    message: str
