"""stores say where they deliver; a product can differ from its store

Revision ID: b9d5f3a1c7e2
Revises: a7c4e2f9b1d3
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op

revision = "b9d5f3a1c7e2"
down_revision = "a7c4e2f9b1d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("delivery", sa.String(length=16), nullable=False, server_default="domestic"))
    op.add_column("stores", sa.Column("delivery_countries", sa.String(length=1024), nullable=True))
    op.add_column("store_products", sa.Column("delivery", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("store_products", "delivery")
    op.drop_column("stores", "delivery_countries")
    op.drop_column("stores", "delivery")
