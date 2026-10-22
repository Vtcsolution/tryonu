"""where a shopper likes to shop: local shops, worldwide stores, or both

Revision ID: e2a6c4f8b1d3
Revises: d7f3b9e1a5c8
Create Date: 2026-10-22
"""

import sqlalchemy as sa
from alembic import op

revision = "e2a6c4f8b1d3"
down_revision = "d7f3b9e1a5c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch:
        batch.add_column(sa.Column("shop_from", sa.String(length=12), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch:
        batch.drop_column("shop_from")
