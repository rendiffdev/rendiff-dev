"""Add job progress tracking columns

Revision ID: 004
Revises: 003
Create Date: 2025-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003_add_performance_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new progress tracking columns to jobs table."""
    # Add current_stage column (alias for stage compatibility)
    op.add_column('jobs', sa.Column('current_stage', sa.String(), nullable=True, server_default='queued'))

    # Add status_message column for progress messages
    op.add_column('jobs', sa.Column('status_message', sa.String(), nullable=True))

    # Add updated_at column for tracking last update
    op.add_column('jobs', sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Add processing_stats column for detailed stats (JSON)
    op.add_column('jobs', sa.Column('processing_stats', sa.JSON(), nullable=True))

    # Sync current_stage with existing stage values
    op.execute("UPDATE jobs SET current_stage = stage WHERE current_stage IS NULL")


def downgrade() -> None:
    """Remove progress tracking columns from jobs table."""
    op.drop_column('jobs', 'processing_stats')
    op.drop_column('jobs', 'updated_at')
    op.drop_column('jobs', 'status_message')
    op.drop_column('jobs', 'current_stage')
