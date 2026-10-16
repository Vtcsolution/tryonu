"""contact page messages

Revision ID: a8e2c6f0b4d1
Revises: f4b9d5e1a7c3
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

revision = "a8e2c6f0b4d1"
down_revision = "f4b9d5e1a7c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("topic", sa.String(length=40), nullable=False, server_default="general"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_contact_messages_handled_at", "contact_messages", ["handled_at"])


def downgrade() -> None:
    op.drop_index("ix_contact_messages_handled_at", table_name="contact_messages")
    op.drop_table("contact_messages")
