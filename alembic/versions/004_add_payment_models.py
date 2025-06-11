"""Add payment and order models

Revision ID: 004_add_payment_models
Revises: 003_add_session_table
Create Date: 2025-01-06 12:00:00.000000

"""
import alembic.op as op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_add_payment_models'
down_revision = '003_add_session_table'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types if they don't exist
    conn = op.get_bind()
    
    # Check for paymentstatus enum
    result = conn.execute(sa.text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'paymentstatus')"))
    if not result.scalar():
        payment_status_enum = postgresql.ENUM(
            'requires_payment_method',
            'requires_confirmation', 
            'requires_action',
            'processing',
            'requires_capture',
            'canceled',
            'succeeded',
            name='paymentstatus'
        )
        payment_status_enum.create(conn)
    
    # Check for orderstatus enum
    result = conn.execute(sa.text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'orderstatus')"))
    if not result.scalar():
        order_status_enum = postgresql.ENUM(
            'draft',
            'payment_pending',
            'payment_authorized',
            'kyc_pending',
            'processing',
            'completed',
            'failed',
            'canceled',
            name='orderstatus'
        )
        order_status_enum.create(conn)
    
    # Create reference-only enum objects for table definitions
    payment_status_ref = postgresql.ENUM(name='paymentstatus', create_type=False)
    order_status_ref = postgresql.ENUM(name='orderstatus', create_type=False)

    # Create orders table
    op.create_table('orders',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('tonnes_co2', sa.Integer(), nullable=False),
        sa.Column('amount_usd', sa.DECIMAL(precision=10, scale=2), nullable=False),
        sa.Column('fee_usd', sa.DECIMAL(precision=10, scale=2), nullable=False),
        sa.Column('total_usd', sa.DECIMAL(precision=10, scale=2), nullable=False),
        sa.Column('eth_address', sa.String(length=42), nullable=True),
        sa.Column('tokens_to_mint', sa.DECIMAL(precision=18, scale=6), nullable=True),
        sa.Column('status', order_status_ref, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create payment_intent table
    op.create_table('payment_intent',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=False),
        sa.Column('client_secret', sa.String(length=255), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('status', payment_status_ref, nullable=False),
        sa.Column('capture_method', sa.String(length=20), nullable=False),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('captured_amount_cents', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_payment_intent_id')
    )


def downgrade():
    op.drop_table('payment_intent')
    op.drop_table('orders')
    
    # Drop enums
    op.execute('DROP TYPE orderstatus')
    op.execute('DROP TYPE paymentstatus')