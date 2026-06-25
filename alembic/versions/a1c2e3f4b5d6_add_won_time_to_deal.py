"""add won_time to Deal

Revision ID: a1c2e3f4b5d6
Revises: f3a1b2c4d5e6
Create Date: 2026-06-25 14:50:00.000000

Phase 5.3: adds a nullable timezone-aware `won_time` column to `deals`,
populated from Pipedrive v2's `won_time` field during sync. Indexed to
support the agent's date-range filters (5.4).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c2e3f4b5d6'
down_revision: Union[str, Sequence[str], None] = 'f3a1b2c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'deals',
        sa.Column('won_time', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f('ix_deals_won_time'), 'deals', ['won_time'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_deals_won_time'), table_name='deals')
    op.drop_column('deals', 'won_time')
