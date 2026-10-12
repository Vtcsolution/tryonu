"""store plans that renew automatically (PayPal subscriptions) and product views

Revision ID: e5f1c9a4b7d8
Revises: d4e0b8f3a6c7
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op

revision = "e5f1c9a4b7d8"
down_revision = "d4e0b8f3a6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # the PayPal product + billing plan made for a store plan, and what they were made for
    op.add_column("store_plans", sa.Column("paypal_product_id", sa.String(length=64), nullable=True))
    op.add_column("store_plans", sa.Column("paypal_plan_id", sa.String(length=64), nullable=True))
    op.add_column("store_plans", sa.Column("paypal_plan_key", sa.String(length=120), nullable=True))

    op.add_column("stores", sa.Column("subscription_id", sa.String(length=64), nullable=True))
    op.add_column("stores", sa.Column("subscription_plan_code", sa.String(length=32), nullable=True))
    op.add_column("stores", sa.Column("subscription_status", sa.String(length=24), nullable=True))
    op.add_column("stores", sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("stores", sa.Column("subscription_last_paid_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_stores_subscription_id", "stores", ["subscription_id"])

    op.create_table(
        "store_product_views",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_product_id", sa.String(length=36), sa.ForeignKey("store_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("store_product_id", "day", name="uq_store_product_views_day"),
    )
    op.create_index("ix_store_product_views_id", "store_product_views", ["id"])
    op.create_index("ix_store_product_views_store_day", "store_product_views", ["store_id", "day"])


def downgrade() -> None:
    op.drop_table("store_product_views")
    op.drop_index("ix_stores_subscription_id", table_name="stores")
    for column in ("subscription_last_paid_at", "auto_renew", "subscription_status", "subscription_plan_code", "subscription_id"):
        op.drop_column("stores", column)
    for column in ("paypal_plan_key", "paypal_plan_id", "paypal_product_id"):
        op.drop_column("store_plans", column)
