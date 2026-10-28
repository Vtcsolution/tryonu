"""two-step sign-in: an authenticator-app code as well as the password

Revision ID: d6a8c0e2f4b5
Revises: c5f7b9d1e3a4
"""

import sqlalchemy as sa
from alembic import op

revision = "d6a8c0e2f4b5"
down_revision = "c5f7b9d1e3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("totp_secret", sa.String(255), nullable=True))
        batch.add_column(sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("totp_enabled")
        batch.drop_column("totp_secret")
