"""find the look: members' photo searches

Revision ID: e5a9c3f1d7b4
Revises: d2f6b8a4c0e3
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from alembic import op

revision = "e5a9c3f1d7b4"
down_revision = "d2f6b8a4c0e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visual_searches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_key", sa.String(length=512), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("height", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="upload"),
        sa.Column("summary", sa.String(length=300), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_visual_searches_user_id", "visual_searches", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_visual_searches_user_id", table_name="visual_searches")
    op.drop_table("visual_searches")
