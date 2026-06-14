"""Leads classification and aggregation service.

Functions take db: Session as the first parameter — Depends() wiring belongs
in app/routers/leads.py, not here (pattern from 02-PATTERNS.md / kpis.py).
"""
from sqlalchemy import Integer, desc, func
from sqlalchemy.orm import Session

from app.models import Lead, Talent

# D-38 (RESEARCH.md Calificado Definition): verified against 730 live rows.
# Average score for this status: 75.4. Do NOT use partial string match — emoji included.
QUALIFIED_STATUS = "✅ Aprobado - Respuesta enviada"

# UI display labels — raw Sheet strings → Spanish display labels (no emoji in UI)
STATUS_DISPLAY = {
    "✅ Aprobado - Respuesta enviada": "Aprobado",
    "🚫 Remitente bloqueado": "Bloqueado",
    "En revisión": "En revisión",
}


def resolve_talent_id(db: Session, talent_name: str) -> int | None:
    """Return talent.id for exact name match, or None for empty/unknown names.

    Exact match is case-sensitive (D-33 — Sheet values are verbatim talent names).
    Empty string or whitespace-only → None (Sin talento asignado bucket).
    """
    if not talent_name or not talent_name.strip():
        return None
    talent = db.query(Talent).filter(Talent.name == talent_name.strip()).first()
    return talent.id if talent is not None else None


def leads_summary(db: Session) -> dict:
    """Return total lead count and calificados count.

    calificados = leads with status_filtrado == QUALIFIED_STATUS only.
    """
    leads_totales = db.query(func.count(Lead.id)).scalar() or 0
    calificados = (
        db.query(func.count(Lead.id))
        .filter(Lead.status_filtrado == QUALIFIED_STATUS)
        .scalar()
        or 0
    )
    return {
        "leads_totales": leads_totales,
        "calificados": calificados,
    }


def leads_by_talent(db: Session) -> list[dict]:
    """Return per-talent lead totals + calificados, ordered by total descending.

    Uses outerjoin so talents with zero leads appear with total=0.
    Appends a "Sin talento asignado" bucket when any leads have talent_id IS NULL.
    """
    rows = (
        db.query(
            Talent.id,
            Talent.name,
            func.count(Lead.id).label("total"),
            func.sum(
                func.cast(Lead.status_filtrado == QUALIFIED_STATUS, Integer)
            ).label("calificados"),
        )
        .outerjoin(Lead, Lead.talent_id == Talent.id)
        .group_by(Talent.id)
        .order_by(desc("total"))
        .all()
    )

    results = [
        {
            "talent_id": row[0],
            "name": row[1],
            "total": row[2] or 0,
            "calificados": row[3] or 0,
            "is_sin_talento": False,
        }
        for row in rows
    ]

    # "Sin talento asignado" bucket — separate query on talent_id IS NULL
    sin_row = db.query(func.count(Lead.id)).filter(Lead.talent_id.is_(None)).one()
    sin_count = sin_row[0]

    if sin_count > 0:
        results.append(
            {
                "talent_id": None,
                "name": "Sin talento asignado",
                "total": sin_count,
                "calificados": 0,  # Can't be calificado without a talent
                "is_sin_talento": True,
            }
        )

    return results
