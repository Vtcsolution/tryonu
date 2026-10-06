"""add more products to a finished look, in rounds

A look holds at most 5 products. A shopper who wants more adds them onto the
finished image in a further round; the job records which look it builds on.

Revision ID: a5d2e8c4f190
Revises: e1b6d3a7f402
Create Date: 2026-10-06
"""

import sqlalchemy as sa
from alembic import op

revision = "a5d2e8c4f190"
down_revision = "e1b6d3a7f402"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tryon_jobs", sa.Column("base_job_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_tryon_jobs_base_job_id", "tryon_jobs", "tryon_jobs", ["base_job_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_tryon_jobs_base_job_id", "tryon_jobs", ["base_job_id"])
    op.add_column("tryon_jobs", sa.Column("look_round", sa.Integer(), server_default="1", nullable=False))


def downgrade() -> None:
    op.drop_column("tryon_jobs", "look_round")
    op.drop_index("ix_tryon_jobs_base_job_id", table_name="tryon_jobs")
    op.drop_constraint("fk_tryon_jobs_base_job_id", "tryon_jobs", type_="foreignkey")
    op.drop_column("tryon_jobs", "base_job_id")
