"""add email body, reason, category, truncated flag to leads

Revision ID: e1f2a3b4c5d6
Revises: c3e4a5b6d7f8
Create Date: 2026-06-30

Fase 8 (8.1): full email body + classifier fields for the lead detail modal.
- email_completo, razon_validacion: nullable TEXT (old rows stay valid; D7 fallbacks).
- categoria_detectada: nullable string (Categoria_Detectada exists in the live Sheet;
  added once a real sync revealed it during 8.1).
- email_truncated: NOT NULL boolean, server_default '0' (D8 size cap flag).

D10 is a no-op here: ix_leads_talent_id already exists (created in d48d69b17ea6
and present in the live DB), so no index is added.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'c3e4a5b6d7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('email_completo', sa.Text(), nullable=True))
    op.add_column('leads', sa.Column('razon_validacion', sa.Text(), nullable=True))
    op.add_column('leads', sa.Column('categoria_detectada', sa.String(), nullable=True))
    op.add_column(
        'leads',
        sa.Column('email_truncated', sa.Boolean(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('leads', 'email_truncated')
    op.drop_column('leads', 'categoria_detectada')
    op.drop_column('leads', 'razon_validacion')
    op.drop_column('leads', 'email_completo')
