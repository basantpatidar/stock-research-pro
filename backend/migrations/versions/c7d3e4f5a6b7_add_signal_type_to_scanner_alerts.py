"""add_signal_type_to_scanner_alerts

Revision ID: c7d3e4f5a6b7
Revises: e8f2b4c91d37
Create Date: 2026-05-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'e8f2b4c91d37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('scanner_alerts', sa.Column('signal_type', sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column('scanner_alerts', 'signal_type')
