"""add_broker_orders

Revision ID: f4a8c2d3e5b6
Revises: d8e5f6a7b8c9
Create Date: 2026-05-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f4a8c2d3e5b6'
down_revision: Union[str, Sequence[str], None] = 'd8e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'broker_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('broker', sa.String(length=20), nullable=False),
        sa.Column('broker_order_id', sa.String(length=64), nullable=True),
        sa.Column('mode', sa.String(length=10), nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('side', sa.String(length=4), nullable=False),
        sa.Column('qty', sa.Float(), nullable=False),
        sa.Column('order_type', sa.String(length=12), nullable=False),
        sa.Column('limit_price', sa.Float(), nullable=True),
        sa.Column('stop_price', sa.Float(), nullable=True),
        sa.Column('take_profit_price', sa.Float(), nullable=True),
        sa.Column('time_in_force', sa.String(length=4), nullable=False, server_default='day'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='new'),
        sa.Column('filled_qty', sa.Float(), nullable=False, server_default='0'),
        sa.Column('filled_avg_price', sa.Float(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('filled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_reason', sa.String(length=200), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='manual'),
        sa.Column('scanner_alert_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('client_order_id', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_order_id', name='uq_broker_orders_client_order_id'),
    )
    op.create_index('ix_broker_orders_broker_order_id', 'broker_orders', ['broker_order_id'], unique=False)
    op.create_index('ix_broker_orders_symbol', 'broker_orders', ['symbol'], unique=False)
    op.create_index('ix_broker_orders_status', 'broker_orders', ['status'], unique=False)
    op.create_index('ix_broker_orders_scanner_alert_id', 'broker_orders', ['scanner_alert_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_broker_orders_scanner_alert_id', table_name='broker_orders')
    op.drop_index('ix_broker_orders_status', table_name='broker_orders')
    op.drop_index('ix_broker_orders_symbol', table_name='broker_orders')
    op.drop_index('ix_broker_orders_broker_order_id', table_name='broker_orders')
    op.drop_table('broker_orders')
