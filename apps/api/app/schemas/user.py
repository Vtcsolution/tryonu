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
    is_team: bool = False
    email_verified: bool
    credits_balance: int
    created_at: datetime
    has_password: bool = False


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    # where the shopper lives (ISO alpha-2): stores that deliver there are shown
    country: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    # the page they were going to (a look someone shared): the verification email leads back to it
    next: str | None = Field(default=None, max_length=300)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ChangePasswordRequest(BaseModel):
    # not needed for an account that has no password yet (signed up with Google)
    current_password: str | None = Field(default=None, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = None


class UserPreferenceOut(ORMModel):
    gender: Gender | None
    preferred_categories: list[str] | None
    preferred_sizes: list[str] | None
    preferred_colors: list[str] | None
    preferred_styles: list[str] | None
    preferred_brands: list[str] | None
    favorite_retailers: list[str] | None
    budget_min_cents: int | None
    budget_max_cents: int | None
    country: str | None = None
    shop_from: str | None = None  # local | worldwide | both


class UserPreferenceUpdate(BaseModel):
    gender: Gender | None = None
    preferred_categories: list[str] | None = Field(default=None, max_length=200)
    preferred_sizes: list[str] | None = None
    preferred_colors: list[str] | None = None
    preferred_styles: list[str] | None = None
    preferred_brands: list[str] | None = None
    favorite_retailers: list[str] | None = None
    budget_min_cents: int | None = None
    budget_max_cents: int | None = None
    country: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    shop_from: str | None = Field(default=None, pattern=r"^(local|worldwide|both)$")
