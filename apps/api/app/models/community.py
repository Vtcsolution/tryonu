"""The TryOnU community: members post finished looks, like and comment on each
other's, and follow each other. Only signed-in members can see it. A post is
always the member's own choice (the picture shows them), and they can delete
it at any time; anyone can report a post or comment, and admins can hide it."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CommunityPost(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "community_posts"
    __table_args__ = (UniqueConstraint("user_id", "tryon_job_id", name="uq_community_posts_user_job"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    tryon_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("tryon_jobs.id", ondelete="CASCADE"), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # hidden by an admin (after a report): gone from every feed
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)


class PostLike(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "community_likes"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_community_likes_post_user"),)

    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("community_posts.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)


class PostComment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "community_comments"

    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("community_posts.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    # a reply to another comment on the same post (one level)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("community_comments.id", ondelete="CASCADE"), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Follow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "community_follows"
    __table_args__ = (UniqueConstraint("follower_id", "followee_id", name="uq_community_follows_pair"),)

    follower_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    followee_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)


class CommunityReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "community_reports"

    reporter_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=True)
    comment_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("community_comments.id", ondelete="CASCADE"), nullable=True)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
