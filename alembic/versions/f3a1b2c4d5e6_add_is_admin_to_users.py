"""add is_admin to users

Revision ID: f3a1b2c4d5e6
Revises: d9955ae215ef
Create Date: 2026-06-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f3a1b2c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'd9955ae215ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('users', 'is_admin')
