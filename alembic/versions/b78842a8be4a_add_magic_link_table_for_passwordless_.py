"""Add magic_link table for passwordless authentication

Revision ID: b78842a8be4a
Revises: 002_add_stripe_session_id
Create Date: 2025-06-10 11:06:04.665443

"""
from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b78842a8be4a'
down_revision: Union[str, None] = '002_add_stripe_session_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create magic_link table for passwordless authentication."""
    op.create_table(
        'magic_link',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('token', sa.String(64), nullable=False, comment='Secure random token for authentication'),
        sa.Column('user_id', sa.Uuid(), nullable=False, comment='User this magic link belongs to'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, comment='When the magic link was created'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False, comment='When the magic link expires (5 minutes from creation)'),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True, comment='When the magic link was redeemed'),
        sa.Column('ip_address', sa.String(45), nullable=True, comment='IP address where magic link was requested'),
        sa.Column('user_agent', sa.String(500), nullable=True, comment='User agent where magic link was requested'),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default='false', comment='Whether the magic link has been used'),
        sa.Column('redirect_url', sa.String(500), nullable=True, comment='URL to redirect to after successful authentication'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )


def downgrade() -> None:
    """Drop magic_link table."""
    op.drop_table('magic_link')
