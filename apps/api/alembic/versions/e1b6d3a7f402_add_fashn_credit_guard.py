"""the FASHN spending guard: authorizations and a durable credit ledger

Additive only: two new tables, nothing existing is altered or backfilled.
A fresh database has no authorization, so live FASHN generation stays off
until an operator runs `python -m app.scripts.fashn_authorize`.

Revision ID: e1b6d3a7f402
Revises: d7a2c9e1b004
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "e1b6d3a7f402"
down_revision = "d7a2c9e1b004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fashn_live_authorizations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("budget_credits", sa.Integer(), nullable=False),
        sa.Column("reserved_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=False, server_default="operator"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("reserved_credits >= 0", name="ck_fashn_auth_reserved_nonneg"),
        sa.CheckConstraint("reserved_credits <= budget_credits", name="ck_fashn_auth_within_budget"),
    )
    op.create_index("ix_fashn_live_authorizations_id", "fashn_live_authorizations", ["id"])
    op.create_index("ix_fashn_live_authorizations_status", "fashn_live_authorizations", ["status"])

    op.create_table(
        "fashn_credit_ledger",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "authorization_id",
            sa.String(length=36),
            sa.ForeignKey("fashn_live_authorizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="reserved"),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=32), nullable=False),
        sa.Column("resolution", sa.String(length=8), nullable=True),
        sa.Column("generation_mode", sa.String(length=16), nullable=True),
        sa.Column("purpose", sa.String(length=160), nullable=False, server_default="unspecified"),
        sa.Column("provider_job_id", sa.String(length=255), nullable=True),
        sa.Column("release_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fashn_credit_ledger_id", "fashn_credit_ledger", ["id"])
    op.create_index("ix_fashn_credit_ledger_provider_job_id", "fashn_credit_ledger", ["provider_job_id"])
    op.create_index("ix_fashn_ledger_auth_state", "fashn_credit_ledger", ["authorization_id", "state"])


def downgrade() -> None:
    op.drop_index("ix_fashn_ledger_auth_state", table_name="fashn_credit_ledger")
    op.drop_index("ix_fashn_credit_ledger_provider_job_id", table_name="fashn_credit_ledger")
    op.drop_index("ix_fashn_credit_ledger_id", table_name="fashn_credit_ledger")
    op.drop_table("fashn_credit_ledger")
    op.drop_index("ix_fashn_live_authorizations_status", table_name="fashn_live_authorizations")
    op.drop_index("ix_fashn_live_authorizations_id", table_name="fashn_live_authorizations")
    op.drop_table("fashn_live_authorizations")
