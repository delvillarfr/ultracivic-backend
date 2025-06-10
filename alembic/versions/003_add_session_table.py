"""Add session table for magic link authentication

Revision ID: 003_add_session_table
Revises: b78842a8be4a
Create Date: 2025-06-10 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_session_table'
down_revision: Union[str, None] = 'b78842a8be4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create session table for magic link authentication."""
    op.create_table(
        'session',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('session_token', sa.String(64), nullable=False, comment='Secure session identifier'),
        sa.Column('user_id', sa.Uuid(), nullable=False, comment='User this session belongs to'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, comment='When the session was created'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, comment='When the session expires'),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=False, comment='When the session was last accessed'),
        sa.Column('ip_address', sa.String(45), nullable=True, comment='IP address where session was created'),
        sa.Column('user_agent', sa.String(500), nullable=True, comment='User agent where session was created'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', comment='Whether the session is active'),
        sa.Column('session_data', sa.Text(), nullable=True, comment='JSON data for session (e.g., permissions, preferences)'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_token')
    )


def downgrade() -> None:
    """Drop session table."""
    op.drop_table('session')