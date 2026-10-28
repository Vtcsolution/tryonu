"""user email events: the automatic emails each member was sent

Revision ID: c5f7b9d1e3a4
Revises: b4e6a8c0d2f3
"""

import sqlalchemy as sa
from alembic import op

revision = "c5f7b9d1e3a4"
down_revision = "b4e6a8c0d2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_email_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("ref", sa.String(36), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "kind", "ref", name="uq_user_email_event"),
    )
    op.create_index("ix_user_email_events_user_id", "user_email_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_email_events_user_id", table_name="user_email_events")
    op.drop_table("user_email_events")
