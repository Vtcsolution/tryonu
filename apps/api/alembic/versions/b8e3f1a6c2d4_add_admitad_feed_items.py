"""products from approved Admitad programme feeds

Admitad has no live search; each approved programme's feed is imported
daily into this table and searched next to eBay and AliExpress.

Revision ID: b8e3f1a6c2d4
Revises: a5d2e8c4f190
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision = "b8e3f1a6c2d4"
down_revision = "a5d2e8c4f190"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admitad_feed_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("campaign_name", sa.String(length=200), nullable=False),
        sa.Column("offer_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("old_price_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=False),
        sa.Column("product_url", sa.String(length=2048), nullable=False),
        sa.Column("vendor", sa.String(length=200), nullable=True),
        sa.Column("category", sa.String(length=200), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("campaign_id", "offer_id", name="uq_admitad_feed_items_offer"),
    )
    op.create_index("ix_admitad_feed_items_id", "admitad_feed_items", ["id"])
    op.create_index("ix_admitad_feed_items_campaign_id", "admitad_feed_items", ["campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_admitad_feed_items_campaign_id", table_name="admitad_feed_items")
    op.drop_index("ix_admitad_feed_items_id", table_name="admitad_feed_items")
    op.drop_table("admitad_feed_items")
