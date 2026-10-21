"""WhatsApp for stores, a link on notifications, and admin announcements

Revision ID: c4e8a2d6f1b3
Revises: b9d3f7a1c5e2
Create Date: 2026-10-21
"""

import sqlalchemy as sa
from alembic import op

revision = "c4e8a2d6f1b3"
down_revision = "b9d3f7a1c5e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stores") as batch:
        batch.add_column(sa.Column("whatsapp", sa.String(length=20), nullable=True))
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("url", sa.String(length=300), nullable=True))
    op.create_table(
        "announcements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("url", sa.String(length=300), nullable=True),
        sa.Column("sent_to", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("announcements")
    with op.batch_alter_table("notifications") as batch:
        batch.drop_column("url")
    with op.batch_alter_table("stores") as batch:
        batch.drop_column("whatsapp")
