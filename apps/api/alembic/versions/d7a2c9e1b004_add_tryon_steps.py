"""record each product's FASHN step for a multi-product try-on

Revision ID: d7a2c9e1b004
Revises: c81f2a4d9e60
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "d7a2c9e1b004"
down_revision = "c81f2a4d9e60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tryon_jobs", sa.Column("steps", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tryon_jobs", "steps")
