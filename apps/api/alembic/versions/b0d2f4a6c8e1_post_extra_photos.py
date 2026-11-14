"""community posts with several photos: the 2nd to 10th photo of a post

Revision ID: b0d2f4a6c8e1
Revises: a9c1e3b5d7f9
"""

import sqlalchemy as sa
from alembic import op

revision = "b0d2f4a6c8e1"
down_revision = "a9c1e3b5d7f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("community_posts", sa.Column("extra_media", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("community_posts", "extra_media")
