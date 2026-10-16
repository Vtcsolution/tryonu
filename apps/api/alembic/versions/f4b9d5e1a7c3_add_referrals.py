"""share and earn: referrals and invite codes

Revision ID: f4b9d5e1a7c3
Revises: e3a8c4d0f6b2
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

revision = "f4b9d5e1a7c3"
down_revision = "e3a8c4d0f6b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "referrals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("referrer_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referred_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("referred_user_id", name="uq_referrals_referred_user_id"),
    )
    op.create_index("ix_referrals_referrer_user_id", "referrals", ["referrer_user_id"])
    op.create_table(
        "referral_codes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_referral_codes_user_id"),
    )
    op.create_index("ix_referral_codes_code", "referral_codes", ["code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_referral_codes_code", table_name="referral_codes")
    op.drop_table("referral_codes")
    op.drop_index("ix_referrals_referrer_user_id", table_name="referrals")
    op.drop_table("referrals")
