"""Add performance indexes

Revision ID: 003_add_performance_indexes
Revises: 002_add_api_key_table
Create Date: 2025-01-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_add_performance_indexes'
down_revision = '002_add_api_key_table'
branch_labels = None
depends_on = None

def upgrade():
    """Add performance indexes for frequently queried columns."""
    # Jobs table indexes (ix_jobs_api_key and ix_jobs_status already exist from 001)
    op.create_index(op.f('ix_jobs_created_at'), 'jobs', ['created_at'])
    op.create_index(op.f('ix_jobs_status_api_key'), 'jobs', ['status', 'api_key'])
    op.create_index(op.f('ix_jobs_api_key_created_at'), 'jobs', ['api_key', 'created_at'])
    # API keys indexes already created in migration 002

def downgrade():
    """Remove performance indexes."""
    # Jobs table indexes (only drop ones added by this migration)
    op.drop_index(op.f('ix_jobs_api_key_created_at'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_status_api_key'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_created_at'), table_name='jobs')
    # API keys indexes managed by migration 002