"""An email an admin sent from Admin → Send email: to one address, every
member who gets emails, every shop owner, or the team. Kept so the admin can
see what went out and to how many."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AdminEmail(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "admin_emails"

    # one | members | stores | team | me
    audience: Mapped[str] = mapped_column(String(16), nullable=False)
    to_address: Mapped[str | None] = mapped_column(String(255), nullable=True)  # audience "one"
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # sending | done
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="sending")
    created_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
