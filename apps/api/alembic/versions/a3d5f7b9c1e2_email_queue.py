"""email queue: group emails go out slowly from a saved list, and a daily count

Revision ID: a3d5f7b9c1e2
Revises: f1c3e5a7b9d2
"""

import sqlalchemy as sa
from alembic import op

revision = "a3d5f7b9c1e2"
down_revision = "f1c3e5a7b9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admin_emails") as batch:
        batch.add_column(sa.Column("recipients", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("next_index", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("looks", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("paused_until", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("last_error", sa.String(300), nullable=True))
    op.create_table(
        "email_send_days",
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
    )
    # a group email cut off by the old in-memory sender is finished as it stands
    op.execute("UPDATE admin_emails SET status = 'done' WHERE status = 'sending'")


def downgrade() -> None:
    op.drop_table("email_send_days")
    with op.batch_alter_table("admin_emails") as batch:
        batch.drop_column("last_error")
        batch.drop_column("paused_until")
        batch.drop_column("looks")
        batch.drop_column("next_index")
        batch.drop_column("recipients")
