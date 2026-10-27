"""ready looks (outfits the team publishes for shoppers) and team members

Revision ID: b5d9f3a1c7e4
Revises: a3c7e1f9b5d2
Create Date: 2026-10-27
"""

import sqlalchemy as sa
from alembic import op

revision = "b5d9f3a1c7e4"
down_revision = "a3c7e1f9b5d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("is_team", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "ready_looks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("audience", sa.String(length=12), nullable=False, server_default="women"),
        sa.Column("season", sa.String(length=24), nullable=True),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tryon_job_id", sa.String(length=36), sa.ForeignKey("tryon_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("image_key", sa.String(length=512), nullable=False),
        sa.Column("card_key", sa.String(length=512), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ready_looks_audience", "ready_looks", ["audience"])
    op.create_index("ix_ready_looks_is_published", "ready_looks", ["is_published"])

    op.create_table(
        "ready_look_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("look_id", sa.String(length=36), sa.ForeignKey("ready_looks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("box", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ready_look_items_look_id", "ready_look_items", ["look_id"])


def downgrade() -> None:
    op.drop_index("ix_ready_look_items_look_id", table_name="ready_look_items")
    op.drop_table("ready_look_items")
    op.drop_index("ix_ready_looks_is_published", table_name="ready_looks")
    op.drop_index("ix_ready_looks_audience", table_name="ready_looks")
    op.drop_table("ready_looks")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_team")
