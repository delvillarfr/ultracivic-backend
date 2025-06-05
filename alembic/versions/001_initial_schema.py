"""Initial Ultra Civic schema with authoritative user table

This migration creates the complete Ultra Civic database schema in a single,
idempotent operation. It can be run multiple times safely.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-06-04 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op  # type: ignore[attr-defined]
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the authoritative Ultra Civic schema (idempotent)."""
    
    # Create KYC status enum type (idempotent)
    kyc_status_enum = postgresql.ENUM(
        'unverified', 'pending', 'verified', 'failed',
        name='kyc_status_enum',
        create_type=False  # We'll handle creation manually for idempotency
    )
    
    # Check if enum type exists, create if not
    connection = op.get_bind()
    enum_exists = connection.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'kyc_status_enum'")
    ).fetchone()
    
    if not enum_exists:
        kyc_status_enum.create(connection, checkfirst=True)
    
    # Create user table (idempotent)
    # Check if table exists first
    inspector = sa.inspect(connection)
    if 'user' not in inspector.get_table_names():
        op.create_table(
            'user',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('email', sa.String(), nullable=False),
            sa.Column('hashed_password', sa.String(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('kyc_status', kyc_status_enum, nullable=False, 
                     server_default='unverified', comment='Stripe KYC verification status'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email', name='ix_user_email')
        )
    else:
        # Table exists, ensure all columns are present
        columns = {col['name']: col for col in inspector.get_columns('user')}
        
        # Add missing columns if they don't exist
        if 'is_superuser' not in columns:
            op.add_column('user', sa.Column('is_superuser', sa.Boolean(), 
                                          nullable=False, server_default='false'))
        
        if 'is_verified' not in columns:
            op.add_column('user', sa.Column('is_verified', sa.Boolean(), 
                                          nullable=False, server_default='false'))
        
        # Update kyc_status column to use enum if it's currently a string
        if 'kyc_status' in columns:
            current_type = str(columns['kyc_status']['type'])
            if 'VARCHAR' in current_type or 'TEXT' in current_type:
                # Convert string column to enum
                op.execute("ALTER TABLE \"user\" ALTER COLUMN kyc_status TYPE kyc_status_enum USING kyc_status::kyc_status_enum")
                op.alter_column('user', 'kyc_status', 
                              nullable=False,
                              server_default='unverified',
                              comment='Stripe KYC verification status')


def downgrade() -> None:
    """Remove the Ultra Civic schema."""
    # Drop table and enum type
    op.drop_table('user')
    
    # Drop enum type
    connection = op.get_bind()
    enum_exists = connection.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'kyc_status_enum'")
    ).fetchone()
    
    if enum_exists:
        op.execute("DROP TYPE kyc_status_enum")