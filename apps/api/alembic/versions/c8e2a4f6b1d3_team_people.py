"""team people: profiles the TryOnU team posts Ready looks to the community as

Revision ID: c8e2a4f6b1d3
Revises: b5d9f3a1c7e4
Create Date: 2026-10-27
"""

import sqlalchemy as sa
from alembic import op

revision = "c8e2a4f6b1d3"
down_revision = "b5d9f3a1c7e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("team_person", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("team_person")
