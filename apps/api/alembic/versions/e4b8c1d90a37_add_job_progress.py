"""say what a try-on is doing while it runs

A multi-item look can take a minute or two of real render time. Without
this the customer sees a timer and nothing else; with it the same wait
reads as work ("Redrawing the watch on its own for a closer match").

Revision ID: e4b8c1d90a37
Revises: c9a51e73b204
Create Date: 2026-09-24
"""

import sqlalchemy as sa
from alembic import op

revision = "e4b8c1d90a37"
down_revision = "c9a51e73b204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tryon_jobs", sa.Column("progress", sa.String(length=160), nullable=True))


def downgrade() -> None:
    op.drop_column("tryon_jobs", "progress")
