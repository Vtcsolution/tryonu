"""credit packs for new members only, and the $1 first-outfit offer (10 credits)

Revision ID: a3c7e1f9b5d2
Revises: e2a6c4f8b1d3
Create Date: 2026-10-27
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "a3c7e1f9b5d2"
down_revision = "e2a6c4f8b1d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("credit_packages") as batch:
        batch.add_column(sa.Column("new_members_only", sa.Boolean(), nullable=False, server_default=sa.false()))

    # the offer itself: one complete outfit try-on for $1, for a member's first purchase
    bind = op.get_bind()
    exists = bind.execute(sa.text("SELECT 1 FROM credit_packages WHERE new_members_only = :t LIMIT 1"), {"t": True}).first()
    if exists is None:
        packages = sa.table(
            "credit_packages",
            sa.column("id", sa.String),
            sa.column("name", sa.String),
            sa.column("credits", sa.Integer),
            sa.column("price_cents", sa.Integer),
            sa.column("currency", sa.String),
            sa.column("is_active", sa.Boolean),
            sa.column("new_members_only", sa.Boolean),
        )
        op.bulk_insert(
            packages,
            [{"id": str(uuid.uuid4()), "name": "First outfit for $1", "credits": 10, "price_cents": 100,
              "currency": "usd", "is_active": True, "new_members_only": True}],
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM credit_packages WHERE new_members_only = true"))
    with op.batch_alter_table("credit_packages") as batch:
        batch.drop_column("new_members_only")
