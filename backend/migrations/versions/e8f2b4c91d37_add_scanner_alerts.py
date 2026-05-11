"""add_scanner_alerts

Revision ID: e8f2b4c91d37
Revises: a3f9d2c81b45
Create Date: 2026-05-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e8f2b4c91d37'
down_revision: Union[str, Sequence[str], None] = 'a3f9d2c81b45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scanner_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('target_price', sa.Float(), nullable=False),
        sa.Column('stop_price', sa.Float(), nullable=False),
        sa.Column('entry_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('signals', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('session_window', sa.String(length=30), nullable=True),
        sa.Column('vix_at_entry', sa.Float(), nullable=True),
        sa.Column('capital_used', sa.Float(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('outcome_price', sa.Float(), nullable=True),
        sa.Column('outcome_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_pnl_pct', sa.Float(), nullable=True),
        sa.Column('actual_pnl_dollar', sa.Float(), nullable=True),
        sa.Column('resolved_by', sa.String(length=30), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scanner_alerts_ticker', 'scanner_alerts', ['ticker'], unique=False)
    op.create_index('ix_scanner_alerts_status', 'scanner_alerts', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_scanner_alerts_status', table_name='scanner_alerts')
    op.drop_index('ix_scanner_alerts_ticker', table_name='scanner_alerts')
    op.drop_table('scanner_alerts')
