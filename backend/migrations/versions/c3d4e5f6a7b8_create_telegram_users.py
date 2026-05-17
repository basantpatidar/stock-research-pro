"""create telegram_users table

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'c3d4e5f6a7b8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'telegram_users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('chat_id', sa.String(50), nullable=False),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('display_name', sa.String(200), nullable=True),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('registered_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_telegram_users_chat_id', 'telegram_users', ['chat_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_telegram_users_chat_id', table_name='telegram_users')
    op.drop_table('telegram_users')
