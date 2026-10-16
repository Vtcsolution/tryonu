"""A message sent from the website's Contact page; admins read it in Admin → Messages."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ContactMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contact_messages"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(String(40), nullable=False, default="general")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # signed in when they wrote it
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
