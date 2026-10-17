"""community: members post their own photos and videos (not only try-on looks)

Revision ID: f1d4a8b2c6e3
Revises: e9c3f7a1b5d2
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op

revision = "f1d4a8b2c6e3"
down_revision = "e9c3f7a1b5d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("community_posts") as batch:
        batch.alter_column("tryon_job_id", existing_type=sa.String(length=36), nullable=True)
        batch.add_column(sa.Column("media_kind", sa.String(length=16), nullable=False, server_default="tryon"))
        batch.add_column(sa.Column("media_key", sa.String(length=512), nullable=True))
        batch.add_column(sa.Column("poster_key", sa.String(length=512), nullable=True))
        batch.add_column(sa.Column("media_width", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("media_height", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.execute("DELETE FROM community_posts WHERE tryon_job_id IS NULL")
    with op.batch_alter_table("community_posts") as batch:
        batch.drop_column("media_height")
        batch.drop_column("media_width")
        batch.drop_column("poster_key")
        batch.drop_column("media_key")
        batch.drop_column("media_kind")
        batch.alter_column("tryon_job_id", existing_type=sa.String(length=36), nullable=False)
