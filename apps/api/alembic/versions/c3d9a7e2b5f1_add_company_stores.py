"""company stores: stores, their products, store plans; payments for a plan; shopper country

Revision ID: c3d9a7e2b5f1
Revises: b8e3f1a6c2d4
Create Date: 2026-10-12
"""

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "c3d9a7e2b5f1"
down_revision = "b8e3f1a6c2d4"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    plans = op.create_table(
        "store_plans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("product_limit", sa.Integer(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_store_plans_id", "store_plans", ["id"])
    now = datetime.now(timezone.utc)
    # starting plans; prices and limits are edited in Admin -> Stores
    rows = [("basic", "Basic", 1000, 50, 1), ("standard", "Standard", 2500, 200, 2), ("premium", "Premium", 5000, 1000, 3)]
    op.bulk_insert(
        plans,
        [
            {"id": str(uuid.uuid4()), "code": code, "name": name, "price_cents": price, "currency": "usd",
             "product_limit": limit, "duration_days": 30, "position": pos, "is_active": True,
             "created_at": now, "updated_at": now}
            for code, name, price, limit, pos in rows
        ],
    )

    op.create_table(
        "stores",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("website_url", sa.String(length=1024), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("logo_key", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_note", sa.Text(), nullable=True),
        sa.Column("plan_code", sa.String(length=32), nullable=True),
        sa.Column("plan_product_limit", sa.Integer(), nullable=False),
        sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feed_url", sa.String(length=2048), nullable=True),
        sa.Column("feed_last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feed_last_result", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_stores_id", "stores", ["id"])
    op.create_index("ix_stores_slug", "stores", ["slug"], unique=True)
    op.create_index("ix_stores_country", "stores", ["country"])
    op.create_index("ix_stores_status", "stores", ["status"])

    op.create_table(
        "store_products",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.Column("product_url", sa.String(length=2048), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("gender", sa.String(length=16), nullable=False),
        sa.Column("color", sa.String(length=60), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("store_id", "external_id", name="uq_store_products_external"),
    )
    op.create_index("ix_store_products_id", "store_products", ["id"])
    op.create_index("ix_store_products_store_id", "store_products", ["store_id"])

    op.add_column("payments", sa.Column("store_plan_id", sa.String(length=36), nullable=True))
    op.add_column("payments", sa.Column("store_id", sa.String(length=36), nullable=True))
    op.create_foreign_key("fk_payments_store_plan_id", "payments", "store_plans", ["store_plan_id"], ["id"])
    op.create_foreign_key("fk_payments_store_id", "payments", "stores", ["store_id"], ["id"], ondelete="SET NULL")
    op.add_column("user_preferences", sa.Column("country", sa.String(length=2), nullable=True))


def downgrade() -> None:
    op.drop_column("user_preferences", "country")
    op.drop_constraint("fk_payments_store_id", "payments", type_="foreignkey")
    op.drop_constraint("fk_payments_store_plan_id", "payments", type_="foreignkey")
    op.drop_column("payments", "store_id")
    op.drop_column("payments", "store_plan_id")
    op.drop_table("store_products")
    op.drop_table("stores")
    op.drop_table("store_plans")
