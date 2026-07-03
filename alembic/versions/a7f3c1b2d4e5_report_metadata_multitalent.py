"""add report metadata (talent_ids, content_hash); nullable talent_id/file_path

Revision ID: a7f3c1b2d4e5
Revises: e1f2a3b4c5d6
Create Date: 2026-07-02

Fase 9.5: reports are regenerated on demand (no PDF persisted to disk) and can be
consolidated across many talents ("all" / multi).
  - talent_ids: regenerate key — "all" | "10" | "10,11,12" (nullable for old rows).
  - content_hash: sha256 of the last-rendered PDF bytes (audit / change detection).
  - talent_id -> nullable: consolidated reports have no single owning talent.
  - file_path -> nullable: PDFs are no longer written to disk.

Uses batch_alter_table because SQLite cannot ALTER COLUMN nullability in place.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a7f3c1b2d4e5'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('reports') as batch:
        batch.add_column(sa.Column('talent_ids', sa.String(), nullable=True))
        batch.add_column(sa.Column('content_hash', sa.String(), nullable=True))
        batch.alter_column('talent_id', existing_type=sa.Integer(), nullable=True)
        batch.alter_column('file_path', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Best-effort revert: drop the added columns. talent_id/file_path are left
    # nullable — restoring NOT NULL would fail against any consolidated rows that
    # legitimately carry NULLs.
    with op.batch_alter_table('reports') as batch:
        batch.drop_column('content_hash')
        batch.drop_column('talent_ids')
