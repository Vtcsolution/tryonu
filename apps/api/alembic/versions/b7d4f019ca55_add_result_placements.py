"""record where each item ended up on a try-on result

The quality pipeline inspects every item and knows the box it occupies;
that was thrown away when the image was saved. Keeping it lets the result
view label each item on the photo ("1. Kurti", "2. Watch") instead of
only listing them beside it.

Revision ID: b7d4f019ca55
Revises: f1c8e42a7b03
Create Date: 2026-09-23
"""

import sqlalchemy as sa
from alembic import op

revision = "b7d4f019ca55"
down_revision = "f1c8e42a7b03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tryon_results", sa.Column("placements", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tryon_results", "placements")
