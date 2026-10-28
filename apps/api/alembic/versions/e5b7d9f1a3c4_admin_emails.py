"""admin emails: what admins sent from Admin → Send email

Revision ID: e5b7d9f1a3c4
Revises: d4a6c8e0f2b5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5b7d9f1a3c4"
down_revision = "d4a6c8e0f2b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_emails",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("audience", sa.String(16), nullable=False),
        sa.Column("to_address", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="sending"),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("admin_emails")
