"""merge Don Silverio + Don Wicho into a single talent

Revision ID: b2d3f4a5c6e7
Revises: a1c2e3f4b5d6
Create Date: 2026-06-25 15:05:00.000000

Phase 5.2 (D2 / Opción A): "Don Silverio" and "Don Wicho" are never sold
separately (Luis, 25-jun) — they share one Pipedrive product. This migration
collapses the two Talent rows into a single "Don Silverio y Don Wicho",
remapping every FK (deals, leads, deal_stage_events, talent_products) from the
losing talent_id(s) to the surviving (lowest-id) keeper, de-duplicating the
keeper's talent_products by product id, then deleting the losing rows.

Idempotent: on a fresh DB already seeded with only the merged name, it no-ops.

Downgrade (intentionally imperfect, per D2): historical deals cannot be split
back to their original talent. It renames the merged talent to "Don Silverio"
and recreates an empty "Don Wicho" row, restoring the two-name structure.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d3f4a5c6e7'
down_revision: Union[str, Sequence[str], None] = 'a1c2e3f4b5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MERGED_NAME = "Don Silverio y Don Wicho"
_FK_TABLES = ("deals", "leads", "deal_stage_events", "talent_products")


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    rows = bind.execute(
        sa.text(
            "SELECT id FROM talents "
            "WHERE name IN ('Don Silverio', 'Don Wicho', :merged) "
            "ORDER BY id"
        ),
        {"merged": MERGED_NAME},
    ).fetchall()
    if not rows:
        return  # nothing to merge

    ids = [r[0] for r in rows]
    keeper = ids[0]
    losers = ids[1:]

    # Surviving row becomes the merged talent.
    bind.execute(
        sa.text("UPDATE talents SET name = :merged WHERE id = :id"),
        {"merged": MERGED_NAME, "id": keeper},
    )

    # Remap every FK from each losing talent to the keeper, then delete it.
    for loser in losers:
        for table in _FK_TABLES:
            bind.execute(
                sa.text(f"UPDATE {table} SET talent_id = :k WHERE talent_id = :l"),
                {"k": keeper, "l": loser},
            )
        bind.execute(sa.text("DELETE FROM talents WHERE id = :l"), {"l": loser})

    # De-duplicate the keeper's talent_products: both originals pointed at the
    # same shared Pipedrive product, leaving redundant rows after the remap.
    # Keep the lowest id per product (COALESCE so NULL product ids collapse too).
    bind.execute(
        sa.text(
            "DELETE FROM talent_products WHERE talent_id = :k AND id NOT IN ("
            "  SELECT MIN(id) FROM talent_products WHERE talent_id = :k "
            "  GROUP BY COALESCE(pipedrive_product_id, -1)"
            ")"
        ),
        {"k": keeper},
    )


def downgrade() -> None:
    """Downgrade schema (imperfect — see module docstring)."""
    bind = op.get_bind()
    merged = bind.execute(
        sa.text("SELECT id FROM talents WHERE name = :merged"),
        {"merged": MERGED_NAME},
    ).fetchone()
    if merged is None:
        return

    bind.execute(
        sa.text("UPDATE talents SET name = 'Don Silverio' WHERE id = :id"),
        {"id": merged[0]},
    )
    exists = bind.execute(
        sa.text("SELECT id FROM talents WHERE name = 'Don Wicho'")
    ).fetchone()
    if exists is None:
        bind.execute(
            sa.text("INSERT INTO talents (name, active) VALUES ('Don Wicho', 1)")
        )
