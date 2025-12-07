"""Add API Key table

Revision ID: 002_add_api_key_table
Revises: 001_initial_schema
Create Date: 2025-07-11 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_add_api_key_table'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create API keys table."""
    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('key_prefix', sa.String(length=8), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('organization', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_admin', sa.Boolean(), nullable=False, default=False),
        sa.Column('max_concurrent_jobs', sa.Integer(), nullable=False, default=5),
        sa.Column('monthly_limit_minutes', sa.Integer(), nullable=False, default=10000),
        sa.Column('total_requests', sa.Integer(), nullable=False, default=0),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'], unique=True)
    op.create_index('ix_api_keys_key_prefix', 'api_keys', ['key_prefix'])
    op.create_index('ix_api_keys_user_id', 'api_keys', ['user_id'])
    op.create_index('ix_api_keys_organization', 'api_keys', ['organization'])
    op.create_index('ix_api_keys_is_active', 'api_keys', ['is_active'])
    op.create_index('ix_api_keys_created_at', 'api_keys', ['created_at'])
    op.create_index('ix_api_keys_expires_at', 'api_keys', ['expires_at'])
    
    # Add composite index for common queries
    op.create_index('ix_api_keys_active_lookup', 'api_keys', ['is_active', 'revoked_at', 'expires_at'])


def downgrade() -> None:
    """Drop API keys table."""
    # Drop indexes
    op.drop_index('ix_api_keys_active_lookup', table_name='api_keys')
    op.drop_index('ix_api_keys_expires_at', table_name='api_keys')
    op.drop_index('ix_api_keys_created_at', table_name='api_keys')
    op.drop_index('ix_api_keys_is_active', table_name='api_keys')
    op.drop_index('ix_api_keys_organization', table_name='api_keys')
    op.drop_index('ix_api_keys_user_id', table_name='api_keys')
    op.drop_index('ix_api_keys_key_prefix', table_name='api_keys')
    op.drop_index('ix_api_keys_key_hash', table_name='api_keys')
    
    # Drop table
    op.drop_table('api_keys')