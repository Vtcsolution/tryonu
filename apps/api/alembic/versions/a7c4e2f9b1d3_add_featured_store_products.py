"""featured store products: a featured limit per plan, a featured flag per product

Revision ID: a7c4e2f9b1d3
Revises: f6a2d0b5c8e9
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op

revision = "a7c4e2f9b1d3"
down_revision = "f6a2d0b5c8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("store_plans", sa.Column("featured_limit", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("stores", sa.Column("plan_featured_limit", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("store_products", sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()))
    # Basic 10, Standard 20, Premium 50; stores with a plan get their plan's number now
    for code, limit in (("basic", 10), ("standard", 20), ("premium", 50)):
        op.execute(sa.text("UPDATE store_plans SET featured_limit = :n WHERE code = :c").bindparams(n=limit, c=code))
    op.execute(
        "UPDATE stores SET plan_featured_limit = COALESCE("
        "(SELECT featured_limit FROM store_plans WHERE store_plans.code = stores.plan_code), 0)"
    )


def downgrade() -> None:
    op.drop_column("store_products", "is_featured")
    op.drop_column("stores", "plan_featured_limit")
    op.drop_column("store_plans", "featured_limit")
