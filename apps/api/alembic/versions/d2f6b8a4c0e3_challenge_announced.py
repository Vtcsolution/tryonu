"""community: remember when every member was told a challenge started

Revision ID: d2f6b8a4c0e3
Revises: c9e4a2d6f8b1
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from alembic import op

revision = "d2f6b8a4c0e3"
down_revision = "c9e4a2d6f8b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("community_challenges") as batch:
        batch.add_column(sa.Column("announced_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("community_challenges") as batch:
        batch.drop_column("announced_at")
