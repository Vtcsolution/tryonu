"""An email an admin sent from Admin → Send email: to one address, every
member who gets emails, every shop owner, or the team. A group email waits in
a queue and goes out slowly (see admin_email_service), so the mailbox plan's
limits are never hit; it carries its own list of people and the looks shown,
and picks up where it stopped after a restart."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AdminEmail(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "admin_emails"

    # one | members | stores | team | me
    audience: Mapped[str] = mapped_column(String(16), nullable=False)
    to_address: Mapped[str | None] = mapped_column(String(255), nullable=True)  # audience "one"
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # None: a plain message; "looks": looks and links picked for the message
    template: Mapped[str | None] = mapped_column(String(24), nullable=True)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # queued | sending | paused | done
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="sending")
    created_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # the queue: who gets it ([{email, name, user_id}]), how far it got, the looks shown
    recipients: Mapped[list | None] = mapped_column(JSON, nullable=True)
    next_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    looks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # the mail server said "slow down": waits until then, then goes on by itself
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)


class EmailSendDay(Base):
    """How many emails the site sent on one day (UTC), so a mailbox plan's
    daily limit is never passed: group emails and the daily email share it."""

    __tablename__ = "email_send_days"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # 2026-10-28
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
