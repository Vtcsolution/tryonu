from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AuthProvider

if TYPE_CHECKING:
    from app.models.credit import CreditTransaction
    from app.models.photo import UserPhoto
    from app.models.preference import UserPreference


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    auth_provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider, native_enum=False, length=32),
        default=AuthProvider.LOCAL,
        nullable=False,
    )
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Denormalized for fast reads; CreditTransaction is the source of truth
    # and every mutation happens inside the same DB transaction as the
    # ledger row (see services/credit_service.py) so the two never drift.
    credits_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    credit_transactions: Mapped[list["CreditTransaction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    photos: Mapped[list["UserPhoto"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preference: Mapped["UserPreference | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Enables refresh-token revocation/rotation independent of JWT expiry."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)


class PasswordResetToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Short-lived, single-use token emailed to the user for
    forgot/reset-password. Only its SHA-256 hash is stored — same pattern
    as RefreshToken — so a DB leak alone can't be used to reset accounts."""

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
