"""add preferred categories to user preferences

Revision ID: a4d8c2e6f913
Revises: e7a3b91c5d62
Create Date: 2026-09-18 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4d8c2e6f913'
down_revision: Union[str, None] = 'e7a3b91c5d62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('user_preferences') as batch_op:
        batch_op.add_column(sa.Column('preferred_categories', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('user_preferences') as batch_op:
        batch_op.drop_column('preferred_categories')
