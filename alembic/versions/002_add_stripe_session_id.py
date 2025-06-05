"""Add Stripe verification session ID for audit trail

This migration adds the stripe_verification_session_id field to the user table
to track Stripe Identity verification sessions for audit and debugging purposes.

Revision ID: 002_add_stripe_session_id
Revises: 001_initial_schema
Create Date: 2025-06-05 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_stripe_session_id'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add stripe_verification_session_id column to user table."""
    op.add_column(
        'user',
        sa.Column(
            'stripe_verification_session_id',
            sa.String(),
            nullable=True,
            comment='Stripe Identity verification session ID for audit trail'
        )
    )


def downgrade() -> None:
    """Remove stripe_verification_session_id column from user table."""
    op.drop_column('user', 'stripe_verification_session_id')