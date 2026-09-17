from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class AdminAuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only record of every state-changing admin action (credit
    adjustments, suspensions, role changes, hiding products, ...), so any
    one admin's changes stay attributable once there's more than one."""

    __tablename__ = "admin_audit_logs"

    admin_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    admin: Mapped["User | None"] = relationship()
