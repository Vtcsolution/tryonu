"""a shopper's saved, favourited and purchased products

Only products someone actually interacted with are stored, never a
retailer's catalogue. Each row is a snapshot — name, image, links and the
price at that moment — so the list survives the retailer editing or
removing the listing, and the affiliate URL saved with it keeps earning
when they open it again.

Revision ID: c9a51e73b204
Revises: b7d4f019ca55
Create Date: 2026-09-23
"""

import sqlalchemy as sa
from alembic import op

revision = "c9a51e73b204"
down_revision = "b7d4f019ca55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_products",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("retailer_slug", sa.String(length=64), nullable=False),
        sa.Column("retailer_product_id", sa.String(length=255), nullable=False),
        sa.Column("retailer_name", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("product_url", sa.String(length=1024), nullable=False),
        sa.Column("affiliate_url", sa.String(length=1024), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "retailer_slug", "retailer_product_id", name="uq_saved_product_per_user"),
    )
    op.create_index("ix_saved_products_user_id", "saved_products", ["user_id"])
    op.create_index("ix_saved_products_user_status", "saved_products", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_saved_products_user_status", table_name="saved_products")
    op.drop_index("ix_saved_products_user_id", table_name="saved_products")
    op.drop_table("saved_products")
