from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AppSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An admin-panel override for one whitelisted Settings field (see
    app/core/runtime_settings.py). The value is always stored Fernet-
    encrypted — several of these are live payment/API credentials."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
