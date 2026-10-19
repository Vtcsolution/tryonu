"""community: replies to replies, likes on comments, photos and looks in
comments, and outside links taken out of captions and comments

Revision ID: a3c7e1f5b9d2
Revises: f1d4a8b2c6e3
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from alembic import op

revision = "a3c7e1f5b9d2"
down_revision = "f1d4a8b2c6e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("community_comments") as batch:
        batch.add_column(sa.Column("image_key", sa.String(length=512), nullable=True))
        batch.add_column(sa.Column("tryon_job_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("links_removed", sa.Integer(), nullable=False, server_default="0"))
        batch.create_foreign_key(
            "fk_community_comments_tryon_job", "tryon_jobs", ["tryon_job_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_community_comments_parent_id", ["parent_id"])
    with op.batch_alter_table("community_posts") as batch:
        batch.add_column(sa.Column("links_removed", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "community_comment_likes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("comment_id", sa.String(length=36), sa.ForeignKey("community_comments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("comment_id", "user_id", name="uq_community_comment_likes_pair"),
    )
    op.create_index("ix_community_comment_likes_comment_id", "community_comment_likes", ["comment_id"])
    op.create_index("ix_community_comment_likes_user_id", "community_comment_likes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_community_comment_likes_user_id", table_name="community_comment_likes")
    op.drop_index("ix_community_comment_likes_comment_id", table_name="community_comment_likes")
    op.drop_table("community_comment_likes")
    with op.batch_alter_table("community_posts") as batch:
        batch.drop_column("links_removed")
    with op.batch_alter_table("community_comments") as batch:
        batch.drop_index("ix_community_comments_parent_id")
        batch.drop_constraint("fk_community_comments_tryon_job", type_="foreignkey")
        batch.drop_column("links_removed")
        batch.drop_column("like_count")
        batch.drop_column("tryon_job_id")
        batch.drop_column("image_key")
