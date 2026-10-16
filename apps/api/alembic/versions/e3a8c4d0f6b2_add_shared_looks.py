"""shared looks: a try-on result its owner shares as a public link

Revision ID: e3a8c4d0f6b2
Revises: d2f7b3c9e1a4
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

revision = "e3a8c4d0f6b2"
down_revision = "d2f7b3c9e1a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shared_looks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("token", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tryon_job_id", sa.String(length=36), sa.ForeignKey("tryon_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_shared_looks_token", "shared_looks", ["token"], unique=True)
    op.create_index("ix_shared_looks_tryon_job_id", "shared_looks", ["tryon_job_id"])


def downgrade() -> None:
    op.drop_index("ix_shared_looks_tryon_job_id", table_name="shared_looks")
    op.drop_index("ix_shared_looks_token", table_name="shared_looks")
    op.drop_table("shared_looks")
