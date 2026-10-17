"""community: posts, likes, comments, follows, reports; usernames and bios

Revision ID: e9c3f7a1b5d2
Revises: d8b2e6c4a9f1
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op

revision = "e9c3f7a1b5d2"
down_revision = "d8b2e6c4a9f1"
branch_labels = None
depends_on = None


def _stamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("users", sa.Column("handle", sa.String(length=30), nullable=True))
    op.add_column("users", sa.Column("bio", sa.String(length=280), nullable=True))
    op.add_column("users", sa.Column("community_banned_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_handle", "users", ["handle"], unique=True)

    op.create_table(
        "community_posts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tryon_job_id", sa.String(length=36), sa.ForeignKey("tryon_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_stamps(),
        sa.UniqueConstraint("user_id", "tryon_job_id", name="uq_community_posts_user_job"),
    )
    op.create_index("ix_community_posts_user_id", "community_posts", ["user_id"])
    op.create_index("ix_community_posts_is_hidden", "community_posts", ["is_hidden"])

    op.create_table(
        "community_likes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("post_id", sa.String(length=36), sa.ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        *_stamps(),
        sa.UniqueConstraint("post_id", "user_id", name="uq_community_likes_post_user"),
    )
    op.create_index("ix_community_likes_post_id", "community_likes", ["post_id"])
    op.create_index("ix_community_likes_user_id", "community_likes", ["user_id"])

    op.create_table(
        "community_comments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("post_id", sa.String(length=36), sa.ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.String(length=36), sa.ForeignKey("community_comments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_stamps(),
    )
    op.create_index("ix_community_comments_post_id", "community_comments", ["post_id"])
    op.create_index("ix_community_comments_user_id", "community_comments", ["user_id"])

    op.create_table(
        "community_follows",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("follower_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("followee_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        *_stamps(),
        sa.UniqueConstraint("follower_id", "followee_id", name="uq_community_follows_pair"),
    )
    op.create_index("ix_community_follows_follower_id", "community_follows", ["follower_id"])
    op.create_index("ix_community_follows_followee_id", "community_follows", ["followee_id"])

    op.create_table(
        "community_reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("reporter_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("post_id", sa.String(length=36), sa.ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("comment_id", sa.String(length=36), sa.ForeignKey("community_comments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        *_stamps(),
    )
    op.create_index("ix_community_reports_resolved_at", "community_reports", ["resolved_at"])


def downgrade() -> None:
    op.drop_table("community_reports")
    op.drop_table("community_follows")
    op.drop_table("community_comments")
    op.drop_table("community_likes")
    op.drop_table("community_posts")
    op.drop_index("ix_users_handle", table_name="users")
    op.drop_column("users", "community_banned_at")
    op.drop_column("users", "bio")
    op.drop_column("users", "handle")
