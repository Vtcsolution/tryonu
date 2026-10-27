"""ready looks: the outfit picture's layout (where each product card goes), so
the page can show the cards as links over the try-on picture

Revision ID: d4a6c8e0f2b5
Revises: c8e2a4f6b1d3
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "d4a6c8e0f2b5"
down_revision = "c8e2a4f6b1d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ready_looks") as batch:
        batch.add_column(sa.Column("layout", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ready_looks") as batch:
        batch.drop_column("layout")
