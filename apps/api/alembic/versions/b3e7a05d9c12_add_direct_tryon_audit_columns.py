"""keep the audit trail of a direct FASHN try-on

The direct engine returns FASHN's output untouched, so what we can offer
instead of post-processing is a record: the QC report (measurements only)
and the engine metadata (model, resolution, mode, provider job id,
timestamps, hash of the stored bytes).

Revision ID: b3e7a05d9c12
Revises: a1f6c3d8b254
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "b3e7a05d9c12"
down_revision = "a1f6c3d8b254"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tryon_results", sa.Column("qc_report", sa.JSON(), nullable=True))
    op.add_column("tryon_results", sa.Column("engine_meta", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tryon_results", "engine_meta")
    op.drop_column("tryon_results", "qc_report")
