"""admin emails: which template (the trending-looks email)

Revision ID: f1c3e5a7b9d2
Revises: e5b7d9f1a3c4
"""

import sqlalchemy as sa
from alembic import op

revision = "f1c3e5a7b9d2"
down_revision = "e5b7d9f1a3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admin_emails") as batch:
        batch.add_column(sa.Column("template", sa.String(24), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("admin_emails") as batch:
        batch.drop_column("template")
