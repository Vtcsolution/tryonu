"""try-on reports: a shopper says a result came out wrong

Revision ID: e7b9d1f3a5c6
Revises: d6a8c0e2f4b5
"""

import sqlalchemy as sa
from alembic import op

revision = "e7b9d1f3a5c6"
down_revision = "d6a8c0e2f4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tryon_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("tryon_jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(24), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="open"),
        sa.Column("credits_refunded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tryon_reports_user_id", "tryon_reports", ["user_id"])
    op.create_index("ix_tryon_reports_status", "tryon_reports", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tryon_reports_status", table_name="tryon_reports")
    op.drop_index("ix_tryon_reports_user_id", table_name="tryon_reports")
    op.drop_table("tryon_reports")
