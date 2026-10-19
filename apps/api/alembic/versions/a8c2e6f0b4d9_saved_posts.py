"""community: members bookmark posts to come back to

Revision ID: a8c2e6f0b4d9
Revises: f7b1d5e9a3c6
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from alembic import op

revision = "a8c2e6f0b4d9"
down_revision = "f7b1d5e9a3c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_saved_posts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("post_id", sa.String(length=36), sa.ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "post_id", name="uq_community_saved_posts_pair"),
    )
    op.create_index("ix_community_saved_posts_user_id", "community_saved_posts", ["user_id"])
    op.create_index("ix_community_saved_posts_post_id", "community_saved_posts", ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_community_saved_posts_post_id", table_name="community_saved_posts")
    op.drop_index("ix_community_saved_posts_user_id", table_name="community_saved_posts")
    op.drop_table("community_saved_posts")
