"""price alerts: tell members when a product gets cheaper or is back in stock

Revision ID: f7b1d5e9a3c6
Revises: e5a9c3f1d7b4
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from alembic import op

revision = "f7b1d5e9a3c6"
down_revision = "e5a9c3f1d7b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_watches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_price_cents", sa.Integer(), nullable=False),
        sa.Column("told_price_cents", sa.Integer(), nullable=True),
        sa.Column("last_price_cents", sa.Integer(), nullable=False),
        sa.Column("in_stock", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "product_id", name="uq_price_watches_pair"),
    )
    op.create_index("ix_price_watches_user_id", "price_watches", ["user_id"])
    op.create_index("ix_price_watches_product_id", "price_watches", ["product_id"])
    op.create_index("ix_price_watches_checked_at", "price_watches", ["checked_at"])
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("product_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_notifications_product", "products", ["product_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.drop_constraint("fk_notifications_product", type_="foreignkey")
        batch.drop_column("product_id")
    op.drop_index("ix_price_watches_checked_at", table_name="price_watches")
    op.drop_index("ix_price_watches_product_id", table_name="price_watches")
    op.drop_index("ix_price_watches_user_id", table_name="price_watches")
    op.drop_table("price_watches")
