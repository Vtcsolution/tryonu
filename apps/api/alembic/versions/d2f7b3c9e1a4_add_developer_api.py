"""developer API: accounts, keys, credit packs, try-ons; payments for packs

Revision ID: d2f7b3c9e1a4
Revises: c1e6a4b2d8f3
Create Date: 2026-10-16
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "d2f7b3c9e1a4"
down_revision = "c1e6a4b2d8f3"
branch_labels = None
depends_on = None


def _stamps() -> list:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "developer_accounts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("company_name", sa.String(length=120), nullable=False),
        sa.Column("website", sa.String(length=1024), nullable=True),
        sa.Column("credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        *_stamps(),
    )
    op.create_table(
        "developer_api_keys",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("developer_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="secret"),
        sa.Column("prefix", sa.String(length=24), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("allowed_domains", sa.JSON(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_stamps(),
    )
    op.create_index("ix_developer_api_keys_account", "developer_api_keys", ["account_id"])
    op.create_index("ix_developer_api_keys_key_hash", "developer_api_keys", ["key_hash"], unique=True)
    op.create_table(
        "developer_credit_packs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=32), unique=True, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("tryons", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="usd"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_stamps(),
    )
    op.create_table(
        "developer_tryons",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("developer_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("api_key_id", sa.String(length=36), sa.ForeignKey("developer_api_keys.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tryon_job_id", sa.String(length=36), sa.ForeignKey("tryon_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("refunded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reference", sa.String(length=120), nullable=True),
        *_stamps(),
    )
    op.create_index("ix_developer_tryons_account_created", "developer_tryons", ["account_id", "created_at"])
    op.create_index("ix_developer_tryons_job", "developer_tryons", ["tryon_job_id"])

    with op.batch_alter_table("payments") as batch:
        batch.add_column(sa.Column("developer_pack_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("developer_account_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_payments_developer_pack", "developer_credit_packs", ["developer_pack_id"], ["id"])
        batch.create_foreign_key(
            "fk_payments_developer_account", "developer_accounts", ["developer_account_id"], ["id"], ondelete="SET NULL"
        )

    # One try-on costs TryOnU about $0.43 (4 FASHN credits x 30 PKR); packs keep a margin
    packs = sa.table(
        "developer_credit_packs",
        sa.column("id", sa.String), sa.column("code", sa.String), sa.column("name", sa.String),
        sa.column("tryons", sa.Integer), sa.column("price_cents", sa.Integer), sa.column("currency", sa.String),
        sa.column("position", sa.Integer), sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(packs, [
        {"id": str(uuid.uuid4()), "code": "starter", "name": "Starter", "tryons": 50, "price_cents": 3500,
         "currency": "usd", "position": 1, "is_active": True},
        {"id": str(uuid.uuid4()), "code": "growth", "name": "Growth", "tryons": 250, "price_cents": 15000,
         "currency": "usd", "position": 2, "is_active": True},
        {"id": str(uuid.uuid4()), "code": "scale", "name": "Scale", "tryons": 1000, "price_cents": 50000,
         "currency": "usd", "position": 3, "is_active": True},
    ])


def downgrade() -> None:
    with op.batch_alter_table("payments") as batch:
        batch.drop_constraint("fk_payments_developer_account", type_="foreignkey")
        batch.drop_constraint("fk_payments_developer_pack", type_="foreignkey")
        batch.drop_column("developer_account_id")
        batch.drop_column("developer_pack_id")
    op.drop_index("ix_developer_tryons_job", table_name="developer_tryons")
    op.drop_index("ix_developer_tryons_account_created", table_name="developer_tryons")
    op.drop_table("developer_tryons")
    op.drop_table("developer_credit_packs")
    op.drop_index("ix_developer_api_keys_key_hash", table_name="developer_api_keys")
    op.drop_index("ix_developer_api_keys_account", table_name="developer_api_keys")
    op.drop_table("developer_api_keys")
    op.drop_table("developer_accounts")
