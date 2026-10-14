"""stores: whether the current plan was given free by an admin

Revision ID: f6a2d0b5c8e9
Revises: e5f1c9a4b7d8
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op

revision = "f6a2d0b5c8e9"
down_revision = "e5f1c9a4b7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("plan_free", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("stores", "plan_free")
