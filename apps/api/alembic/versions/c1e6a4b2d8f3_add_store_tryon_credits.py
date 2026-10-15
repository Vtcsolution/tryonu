"""store try-on credits: plans include shopper try-ons the store pays for

Revision ID: c1e6a4b2d8f3
Revises: b9d5f3a1c7e2
Create Date: 2026-10-15
"""

import sqlalchemy as sa
from alembic import op

revision = "c1e6a4b2d8f3"
down_revision = "b9d5f3a1c7e2"
branch_labels = None
depends_on = None

# One try-on costs TryOnU 4 FASHN credits x 30 PKR = 120 PKR (about $0.43).
# Plans priced to keep a margin after those costs and PayPal's fee:
#   Basic    $15  /   50 products / 10 featured /  20 try-ons (try-ons cost ~$8.60)
#   Standard $45  /  200 products / 20 featured /  60 try-ons (~$25.70)
#   Premium  $110 / 1000 products / 50 featured / 150 try-ons (~$64.30)
_PLANS = (("basic", 1500, 20), ("standard", 4500, 60), ("premium", 11000, 150))


def upgrade() -> None:
    op.add_column("store_plans", sa.Column("tryon_credits", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("stores", sa.Column("tryon_credits", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "store_tryons",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "store_product_id", sa.String(length=36), sa.ForeignKey("store_products.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("tryon_job_id", sa.String(length=36), sa.ForeignKey("tryon_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paid_by_store", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("shared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("refunded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("shopper_country", sa.String(length=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_store_tryons_store_created", "store_tryons", ["store_id", "created_at"])
    op.create_index("ix_store_tryons_job", "store_tryons", ["tryon_job_id"])
    for code, price, tryons in _PLANS:
        op.execute(
            sa.text("UPDATE store_plans SET price_cents = :p, tryon_credits = :t WHERE code = :c").bindparams(
                p=price, t=tryons, c=code
            )
        )
    # stores with a plan now get their plan's try-on credits
    op.execute(
        "UPDATE stores SET tryon_credits = COALESCE("
        "(SELECT tryon_credits FROM store_plans WHERE store_plans.code = stores.plan_code), 0) "
        "WHERE plan_expires_at > CURRENT_TIMESTAMP"
    )


def downgrade() -> None:
    op.drop_index("ix_store_tryons_job", table_name="store_tryons")
    op.drop_index("ix_store_tryons_store_created", table_name="store_tryons")
    op.drop_table("store_tryons")
    op.drop_column("stores", "tryon_credits")
    op.drop_column("store_plans", "tryon_credits")
