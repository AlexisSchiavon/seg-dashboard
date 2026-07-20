"""add insights_cache table

Revision ID: f4a1b2c3d4e5
Revises: c9f5a2b3d4e8
Create Date: 2026-07-19

Módulo 1 / Insights por IA: cache de insights ejecutivos generados por el
agente para el Resumen. Una fila por cache_key (ej. 'resumen').
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f4a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'c9f5a2b3d4e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'insights_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cache_key', sa.String(), nullable=False),
        sa.Column('content_json', sa.Text(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_insights_cache_cache_key', 'insights_cache',
                    ['cache_key'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_insights_cache_cache_key', table_name='insights_cache')
    op.drop_table('insights_cache')
