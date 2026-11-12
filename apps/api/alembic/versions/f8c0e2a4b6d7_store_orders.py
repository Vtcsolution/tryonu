"""store orders: customers order from a store's own page (tryonu.app/<store>)

Revision ID: f8c0e2a4b6d7
Revises: e7b9d1f3a5c6
"""

import sqlalchemy as sa
from alembic import op

revision = "f8c0e2a4b6d7"
down_revision = "e7b9d1f3a5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "store_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("store_id", sa.String(36), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.String(16), nullable=False, unique=True),
        sa.Column("customer_name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="new"),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_store_orders_store_created", "store_orders", ["store_id", "created_at"])
    op.create_index("ix_store_orders_status", "store_orders", ["status"])


def downgrade() -> None:
    op.drop_index("ix_store_orders_status", table_name="store_orders")
    op.drop_index("ix_store_orders_store_created", table_name="store_orders")
    op.drop_table("store_orders")
