"""add_five_min_direction_to_scanner_alerts

Revision ID: d8e5f6a7b8c9
Revises: c7d3e4f5a6b7
Create Date: 2026-05-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c7d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('scanner_alerts', sa.Column('five_min_direction', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('scanner_alerts', 'five_min_direction')
