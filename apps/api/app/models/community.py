"""The TryOnU community: members post finished looks, like and comment on each
other's, and follow each other. Only signed-in members can see it. A post is
always the member's own choice (the picture shows them), and they can delete
it at any time; anyone can report a post or comment, and admins can hide it."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CommunityPost(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "community_posts"
    __table_args__ = (UniqueConstraint("user_id", "tryon_job_id", name="uq_community_posts_user_job"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    # a try-on look (tryon_job_id), or a photo/video the member uploaded (media_key)
    tryon_job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tryon_jobs.id", ondelete="CASCADE"), nullable=True)
    media_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="tryon")  # tryon | image | video
    media_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    poster_key: Mapped[str | None] = mapped_column(String(512), nullable=True)  # a video's cover picture
    media_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # outside links taken out of the caption (only TryOnU links may be shared)
    links_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # "Buy or skip?": the member asked the community, and the votes so far
    poll: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    poll_buy: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    poll_skip: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # an entry in a weekly style challenge
    challenge_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("community_challenges.id", ondelete="SET NULL"), index=True, nullable=True
    )
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
    # a reply to another comment on the same post (replies to replies too, like Facebook)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("community_comments.id", ondelete="CASCADE"), index=True, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # a photo the member added, or one of their own try-on looks
    image_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tryon_job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tryon_jobs.id", ondelete="SET NULL"), nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # outside links taken out (only TryOnU links may be shared)
    links_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CommentLike(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "community_comment_likes"
    __table_args__ = (UniqueConstraint("comment_id", "user_id", name="uq_community_comment_likes_pair"),)

    comment_id: Mapped[str] = mapped_column(String(36), ForeignKey("community_comments.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)


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


class PollVote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One member's "Buy it" or "Skip it" on a post that asked."""

    __tablename__ = "community_poll_votes"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_community_poll_votes_pair"),)

    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("community_posts.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    choice: Mapped[str] = mapped_column(String(8), nullable=False)  # buy | skip


class Challenge(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A weekly style challenge: a theme and dates set by an admin; the most
    liked entries win free credits when it ends."""

    __tablename__ = "community_challenges"

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    prize_1: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    prize_2: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    prize_3: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    # a store can sponsor a challenge (shown with its name and logo)
    sponsor_store_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # when every member was told it started
    announced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # when the winners were chosen and paid
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChallengeWinner(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "community_challenge_winners"
    __table_args__ = (UniqueConstraint("challenge_id", "place", name="uq_community_challenge_winners_place"),)

    challenge_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("community_challenges.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    post_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("community_posts.id", ondelete="SET NULL"), nullable=True)
    place: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3
    credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    likes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
