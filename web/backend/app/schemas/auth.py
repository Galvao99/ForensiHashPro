from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: str
    password: str
    accept_terms: bool
    accept_privacy: bool


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    analysis_profile: str
    is_active: bool
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
    privacy: PrivacyResponse
    csrf_token: str
