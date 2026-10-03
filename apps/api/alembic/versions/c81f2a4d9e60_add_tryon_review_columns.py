"""hold unverified and stalled paid try-ons for review

Revision ID: c81f2a4d9e60
Revises: b3e7a05d9c12
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "c81f2a4d9e60"
down_revision = "b3e7a05d9c12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tryon_jobs", sa.Column("review_state", sa.String(length=16), nullable=True))
    op.add_column("tryon_jobs", sa.Column("review_reason", sa.Text(), nullable=True))
    op.add_column("tryon_jobs", sa.Column("review_payload", sa.JSON(), nullable=True))
    op.create_index("ix_tryon_jobs_review_state", "tryon_jobs", ["review_state"])


def downgrade() -> None:
    op.drop_index("ix_tryon_jobs_review_state", table_name="tryon_jobs")
    op.drop_column("tryon_jobs", "review_payload")
    op.drop_column("tryon_jobs", "review_reason")
    op.drop_column("tryon_jobs", "review_state")
