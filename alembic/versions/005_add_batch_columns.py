"""Add batch_id and batch_index columns to jobs table

Revision ID: 005
Revises: 004
Create Date: 2025-01-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add batch_id and batch_index columns to jobs table."""
    # Add batch_id column for batch processing
    op.add_column('jobs', sa.Column('batch_id', sa.String(), nullable=True))

    # Add batch_index column for ordering within a batch
    op.add_column('jobs', sa.Column('batch_index', sa.Integer(), nullable=True))

    # Create index for batch_id for faster batch queries
    op.create_index('ix_jobs_batch_id', 'jobs', ['batch_id'])


def downgrade() -> None:
    """Remove batch columns from jobs table."""
    op.drop_index('ix_jobs_batch_id', 'jobs')
    op.drop_column('jobs', 'batch_index')
    op.drop_column('jobs', 'batch_id')
