"""Who got the free welcome credits, and from where: one row per account,
so the same person can't collect them again with another email address."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WelcomeClaim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "welcome_claims"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    # sha256 of the email with Gmail dots and any "+tag" removed: a.b+1@gmail.com == ab@gmail.com
    email_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # a random id the website keeps in the browser (X-TryOnU-Device)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # granted | same_email | same_device | same_network | disposable_email
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
