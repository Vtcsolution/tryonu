"""Notifications: the bell, phone notifications and the daily email.

One row per thing that happened to a member (someone liked their post,
replied to them, followed them, a friend joined from their link, credits were
added). The words are made when the row is shown, so a renamed member shows
with their new name."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # post_like | comment | reply | comment_like | follow | referral_joined | reward | credits_added
    # | poll_vote | challenge_win | challenge_ended | challenge_started | price_drop | back_in_stock | mention
    # | announcement (a message from TryOnU to every member)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    post_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=True)
    comment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("community_comments.id", ondelete="CASCADE"), nullable=True
    )
    challenge_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("community_challenges.id", ondelete="CASCADE"), nullable=True
    )
    # a product the member watches the price of
    product_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=True)
    credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str | None] = mapped_column(String(300), nullable=True)  # a comment's first words, a reward's reason
    url: Mapped[str | None] = mapped_column(String(300), nullable=True)  # where tapping it goes, when set
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PushSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One phone or browser that said yes to notifications."""

    __tablename__ = "push_subscriptions"
    __table_args__ = (UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(1024), nullable=False)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Announcement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A message an admin sent to every member (the bell and their phones)."""

    __tablename__ = "announcements"

    text: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sent_to: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
