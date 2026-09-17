"""add page views

Revision ID: e7a3b91c5d62
Revises: 9c4f2a7d1e30
Create Date: 2026-09-17 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7a3b91c5d62'
down_revision: Union[str, None] = '9c4f2a7d1e30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'page_views',
        sa.Column('visitor_id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('path', sa.String(length=512), nullable=False),
        sa.Column('referrer_host', sa.String(length=255), nullable=True),
        sa.Column('country', sa.String(length=2), nullable=True),
        sa.Column('device', sa.String(length=16), nullable=False),
        sa.Column('browser', sa.String(length=32), nullable=False),
        sa.Column('os', sa.String(length=32), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_page_views_id'), 'page_views', ['id'], unique=False)
    op.create_index(op.f('ix_page_views_visitor_id'), 'page_views', ['visitor_id'], unique=False)
    op.create_index(op.f('ix_page_views_session_id'), 'page_views', ['session_id'], unique=False)
    op.create_index(op.f('ix_page_views_user_id'), 'page_views', ['user_id'], unique=False)
    op.create_index(op.f('ix_page_views_path'), 'page_views', ['path'], unique=False)
    op.create_index(op.f('ix_page_views_country'), 'page_views', ['country'], unique=False)
    op.create_index('ix_page_views_created_at', 'page_views', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_page_views_created_at', table_name='page_views')
    for col in ('country', 'path', 'user_id', 'session_id', 'visitor_id', 'id'):
        op.drop_index(op.f(f'ix_page_views_{col}'), table_name='page_views')
    op.drop_table('page_views')
