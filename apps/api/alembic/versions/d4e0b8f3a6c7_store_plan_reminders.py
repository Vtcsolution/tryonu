"""store plan reminders: remember which expiry each reminder was sent for

Revision ID: d4e0b8f3a6c7
Revises: c3d9a7e2b5f1
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e0b8f3a6c7"
down_revision = "c3d9a7e2b5f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("reminded_for_expiry", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stores", sa.Column("expired_notice_for", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("stores", "expired_notice_for")
    op.drop_column("stores", "reminded_for_expiry")
