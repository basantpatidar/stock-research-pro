"""add_stock_data_cache

Revision ID: a3f9d2c81b45
Revises: 7b85133c10a8
Create Date: 2026-04-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a3f9d2c81b45'
down_revision: Union[str, Sequence[str], None] = '7b85133c10a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stock_data_cache',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('data_type', sa.String(length=30), nullable=False),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker', 'data_type', name='uq_stock_data_cache_ticker_type'),
    )
    op.create_index('ix_stock_data_cache_ticker', 'stock_data_cache', ['ticker'], unique=False)

    # Widen research_cache.mode (was String(20)) and add unique constraint for upserts
    op.alter_column('research_cache', 'mode', type_=sa.String(100), existing_nullable=False)
    op.create_unique_constraint('uq_research_cache_ticker_mode', 'research_cache', ['ticker', 'mode'])


def downgrade() -> None:
    op.drop_constraint('uq_research_cache_ticker_mode', 'research_cache', type_='unique')
    op.alter_column('research_cache', 'mode', type_=sa.String(20), existing_nullable=False)
    op.drop_index('ix_stock_data_cache_ticker', table_name='stock_data_cache')
    op.drop_table('stock_data_cache')
