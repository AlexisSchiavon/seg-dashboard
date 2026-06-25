"""lowercase existing user emails

Revision ID: c3e4a5b6d7f8
Revises: b2d3f4a5c6e7
Create Date: 2026-06-25 15:15:00.000000

Phase 5.5.1: email is not case-sensitive in practice. Login and all write paths
now normalize to lowercase; this backfills any existing rows so the whole users
table is consistent.

Guard: if two rows would collapse to the same lowercase email (a genuine
case-collision), abort the migration loudly rather than violate the unique
index or silently drop a user — the operator must resolve it manually first.

Downgrade is a no-op: lowercasing is not reversible (the original casing is lost,
and case-insensitive auth makes the distinction meaningless anyway).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e4a5b6d7f8'
down_revision: Union[str, Sequence[str], None] = 'b2d3f4a5c6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    collisions = bind.execute(
        sa.text(
            "SELECT lower(email) AS le, COUNT(*) AS n "
            "FROM users GROUP BY lower(email) HAVING n > 1"
        )
    ).fetchall()
    if collisions:
        offenders = ", ".join(c[0] for c in collisions)
        raise RuntimeError(
            "Cannot lowercase user emails — case-collisions exist for: "
            f"{offenders}. Resolve these rows manually before re-running."
        )

    bind.execute(sa.text("UPDATE users SET email = lower(email) WHERE email != lower(email)"))


def downgrade() -> None:
    """Downgrade schema (no-op — original casing is not recoverable)."""
    pass
