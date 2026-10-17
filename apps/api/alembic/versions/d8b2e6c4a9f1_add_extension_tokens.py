"""browser extensions: sign-in tokens

Revision ID: d8b2e6c4a9f1
Revises: c5f1a9d3e7b8
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op

revision = "d8b2e6c4a9f1"
down_revision = "c5f1a9d3e7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extension_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="shopper"),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_extension_tokens_user_id", "extension_tokens", ["user_id"])
    op.create_index("ix_extension_tokens_token_hash", "extension_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_extension_tokens_token_hash", table_name="extension_tokens")
    op.drop_index("ix_extension_tokens_user_id", table_name="extension_tokens")
    op.drop_table("extension_tokens")
