"""share and earn: rewards for a friend's first try-on and a store's first plan

Revision ID: c5f1a9d3e7b8
Revises: a8e2c6f0b4d1
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op

revision = "c5f1a9d3e7b8"
down_revision = "a8e2c6f0b4d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("referrals", sa.Column("tryon_rewarded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("referrals", sa.Column("store_rewarded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("referrals", sa.Column("store_plan_name", sa.String(length=80), nullable=True))
    # what the person who invited a store earns when it buys this plan
    op.add_column("store_plans", sa.Column("referral_credits", sa.Integer(), nullable=False, server_default="0"))
    op.execute("UPDATE store_plans SET referral_credits = 10 WHERE code = 'basic'")
    op.execute("UPDATE store_plans SET referral_credits = 20 WHERE code = 'standard'")
    op.execute("UPDATE store_plans SET referral_credits = 30 WHERE code = 'premium'")


def downgrade() -> None:
    op.drop_column("store_plans", "referral_credits")
    op.drop_column("referrals", "store_plan_name")
    op.drop_column("referrals", "store_rewarded_at")
    op.drop_column("referrals", "tryon_rewarded_at")
