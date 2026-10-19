"""your size: height, weight and measurements for size suggestions

Revision ID: b9d3f7a1c5e2
Revises: a8c2e6f0b4d9
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from alembic import op

revision = "b9d3f7a1c5e2"
down_revision = "a8c2e6f0b4d9"
branch_labels = None
depends_on = None

COLUMNS = ("height_cm", "weight_kg", "bust_cm", "waist_cm", "hips_cm", "shoe_eu")


def upgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch:
        for name in COLUMNS:
            batch.add_column(sa.Column(name, sa.Integer(), nullable=True))
        batch.add_column(sa.Column("fit", sa.String(length=8), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch:
        batch.drop_column("fit")
        for name in reversed(COLUMNS):
            batch.drop_column(name)
