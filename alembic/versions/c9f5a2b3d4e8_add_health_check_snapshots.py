"""add health_check_snapshots table

Revision ID: c9f5a2b3d4e8
Revises: b8e4d1f2a3c7
Create Date: 2026-07-07

Prompt 3 Feature 2: historical snapshots of data-health checks (count +
affected value + delta) for trend display.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c9f5a2b3d4e8'
down_revision: Union[str, Sequence[str], None] = 'b8e4d1f2a3c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'health_check_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('check_id', sa.String(), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('affected_value', sa.Float(), nullable=False),
        sa.Column('snapshot_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('resolved_delta', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_health_check_snapshots_check_id',
                    'health_check_snapshots', ['check_id'])
    op.create_index('ix_health_check_snapshots_snapshot_at',
                    'health_check_snapshots', ['snapshot_at'])


def downgrade() -> None:
    op.drop_index('ix_health_check_snapshots_snapshot_at',
                  table_name='health_check_snapshots')
    op.drop_index('ix_health_check_snapshots_check_id',
                  table_name='health_check_snapshots')
    op.drop_table('health_check_snapshots')
