"""add_loose_gates_to_scanner_alerts

Revision ID: a1b2c3d4e5f6
Revises: f4a8c2d3e5b6
Create Date: 2026-05-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f4a8c2d3e5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('scanner_alerts', sa.Column('loose_gates', sa.Boolean(), nullable=True, server_default='false'))


def downgrade() -> None:
    op.drop_column('scanner_alerts', 'loose_gates')
