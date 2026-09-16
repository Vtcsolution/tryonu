"""add wardrobe item to tryon jobs

Revision ID: 183dc7670270
Revises: 164e48411da8
Create Date: 2026-09-16 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '183dc7670270'
down_revision: Union[str, None] = '164e48411da8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tryon_jobs') as batch_op:
        batch_op.add_column(sa.Column('wardrobe_item_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            'fk_tryon_jobs_wardrobe_item_id', 'wardrobe_items', ['wardrobe_item_id'], ['id'], ondelete='RESTRICT'
        )


def downgrade() -> None:
    with op.batch_alter_table('tryon_jobs') as batch_op:
        batch_op.drop_constraint('fk_tryon_jobs_wardrobe_item_id', type_='foreignkey')
        batch_op.drop_column('wardrobe_item_id')
