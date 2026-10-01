"""save the "other options" shown alongside each selected item

The real distractor set for the shadow-mode identity check
(app/services/tryon_quality/distractor_rank.py): what the client actually
showed the shopper next to the product they picked, at the moment they
picked it, so verification compares the render against what the shopper
could really have confused it with instead of a same-category guess.

Revision ID: a1f6c3d8b254
Revises: e4b8c1d90a37
Create Date: 2026-10-01
"""

import sqlalchemy as sa
from alembic import op

revision = "a1f6c3d8b254"
down_revision = "e4b8c1d90a37"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tryon_jobs", sa.Column("distractor_options", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tryon_jobs", "distractor_options")
