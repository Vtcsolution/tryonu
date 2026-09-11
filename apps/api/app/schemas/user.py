from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import AuthProvider, Gender
from app.schemas.common import ORMModel


class UserOut(ORMModel):
    id: str
    email: EmailStr
    full_name: str | None
    avatar_url: str | None
    auth_provider: AuthProvider
    is_admin: bool
    email_verified: bool
    credits_balance: int
    created_at: datetime


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = None


class UserPreferenceOut(ORMModel):
    gender: Gender | None
    preferred_sizes: list[str] | None
    preferred_colors: list[str] | None
    preferred_styles: list[str] | None
    preferred_brands: list[str] | None
    favorite_retailers: list[str] | None
    budget_min_cents: int | None
    budget_max_cents: int | None


class UserPreferenceUpdate(BaseModel):
    gender: Gender | None = None
    preferred_sizes: list[str] | None = None
    preferred_colors: list[str] | None = None
    preferred_styles: list[str] | None = None
    preferred_brands: list[str] | None = None
    favorite_retailers: list[str] | None = None
    budget_min_cents: int | None = None
    budget_max_cents: int | None = None
