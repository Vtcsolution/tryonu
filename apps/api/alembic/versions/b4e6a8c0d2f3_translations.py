"""translations: the website's text in other languages, made once and kept

Revision ID: b4e6a8c0d2f3
Revises: a3d5f7b9c1e2
"""

import sqlalchemy as sa
from alembic import op

revision = "b4e6a8c0d2f3"
down_revision = "a3d5f7b9c1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "translations",
        sa.Column("lang", sa.String(8), primary_key=True),
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("translations")
