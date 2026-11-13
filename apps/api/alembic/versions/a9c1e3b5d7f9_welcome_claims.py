"""welcome claims: one free welcome-credit grant per person, not per email

Revision ID: a9c1e3b5d7f9
Revises: f8c0e2a4b6d7
"""

import sqlalchemy as sa
from alembic import op

revision = "a9c1e3b5d7f9"
down_revision = "f8c0e2a4b6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "welcome_claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("email_key", sa.String(64), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("device_id", sa.String(64), nullable=True),
        sa.Column("granted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_welcome_claims_email_key", "welcome_claims", ["email_key"])
    op.create_index("ix_welcome_claims_ip", "welcome_claims", ["ip"])
    op.create_index("ix_welcome_claims_device_id", "welcome_claims", ["device_id"])


def downgrade() -> None:
    op.drop_table("welcome_claims")
