"""community: a free music library, and a song on a post

Revision ID: d7f3b9e1a5c8
Revises: c4e8a2d6f1b3
Create Date: 2026-10-21
"""

import sqlalchemy as sa
from alembic import op

revision = "d7f3b9e1a5c8"
down_revision = "c4e8a2d6f1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_music",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("artist", sa.String(length=120), nullable=True),
        sa.Column("mood", sa.String(length=24), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    with op.batch_alter_table("community_posts") as batch:
        batch.add_column(sa.Column("music_track_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_community_posts_music_track_id", "community_music", ["music_track_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("community_posts") as batch:
        batch.drop_constraint("fk_community_posts_music_track_id", type_="foreignkey")
        batch.drop_column("music_track_id")
    op.drop_table("community_music")
