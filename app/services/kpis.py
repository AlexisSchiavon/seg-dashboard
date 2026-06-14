"""Global KPI aggregation and talent ranking service.

Functions take db: Session as the first parameter — Depends() wiring belongs
in app/routers/dashboard.py, not here (02-PATTERNS.md convention).

Pitfall 4 (global vs per-talent split):
  - Global KPIs: query Deal directly, NO join to Talent — talent_id IS NULL
    rows are included in totals.
  - Ranking: outerjoin Talent←Deal to aggregate per talent, PLUS a separate
    query for the Sin-talento bucket (Deal.talent_id.is_(None)) appended last.
"""

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.models import Deal, Talent


def global_kpis(db: Session) -> dict:
    """Return the 4 KPI tiles for the Resumen tab.

    Returns a dict with key "kpis": list of KpiTile-shaped dicts.

    Tile order: Pipeline total (accent), En negociación (amber),
    Cerrados (purple), En campaña (green).
    """
    # Pipeline total — ALL deals, no talent join (Pitfall 4)
    pipeline_total = db.query(
        func.coalesce(func.sum(Deal.value), 0.0)
    ).scalar() or 0.0

    # En negociación — open deals in "Negociación" stage
    neg_row = db.query(
        func.count(Deal.id),
        func.coalesce(func.sum(Deal.value), 0.0),
    ).filter(
        Deal.stage_name == "Negociación",
        Deal.status == "open",
    ).one()
    neg_count, neg_value = neg_row[0], neg_row[1] or 0.0

    # Cerrados — won deals (all stages)
    won_row = db.query(
        func.count(Deal.id),
        func.coalesce(func.sum(Deal.value), 0.0),
    ).filter(Deal.status == "won").one()
    won_count, won_value = won_row[0], won_row[1] or 0.0

    # En campaña — open deals in "En ejecución" stage (Trello-sourced; 0 until Phase 4)
    campana_row = db.query(
        func.count(Deal.id),
        func.coalesce(func.sum(Deal.value), 0.0),
    ).filter(
        Deal.stage_name == "En ejecución",
        Deal.status == "open",
    ).one()
    campana_count, campana_value = campana_row[0], campana_row[1] or 0.0

    return {
        "kpis": [
            {
                "label": "Pipeline total",
                "value": float(pipeline_total),
                "count": None,
                "variant": "accent",
            },
            {
                "label": "En negociación",
                "value": float(neg_value),
                "count": neg_count,
                "variant": "amber",
            },
            {
                "label": "Cerrados",
                "value": float(won_value),
                "count": won_count,
                "variant": "purple",
            },
            {
                "label": "En campaña",
                "value": float(campana_value),
                "count": campana_count,
                "variant": "green",
            },
        ]
    }


def talent_ranking(db: Session) -> list[dict]:
    """Return per-talent revenue ranking + Sin-talento bucket.

    Ranked by total deal value descending (outerjoin includes talents with 0
    deals). Sin-talento bucket appended last if any talent_id=None deals exist.

    Each row is a dict matching the RankingRow schema shape.
    """
    # Per-talent aggregation via outerjoin so talent rows with 0 deals appear
    rows = (
        db.query(
            Talent.id,
            Talent.name,
            Talent.category,
            func.coalesce(func.sum(Deal.value), 0.0).label("revenue"),
            func.count(Deal.id).label("deal_count"),
        )
        .outerjoin(Deal, Deal.talent_id == Talent.id)
        .group_by(Talent.id)
        .order_by(desc("revenue"))
        .all()
    )

    ranking = [
        {
            "talent_id": row[0],
            "name": row[1],
            "category": row[2],
            "revenue": float(row[3]),
            "deal_count": row[4],
            "is_sin_talento": False,
        }
        for row in rows
    ]

    # Sin-talento bucket (D-17, Pitfall 4) — separate query on talent_id IS NULL
    sin_row = db.query(
        func.count(Deal.id),
        func.coalesce(func.sum(Deal.value), 0.0),
    ).filter(Deal.talent_id.is_(None)).one()
    sin_count, sin_revenue = sin_row[0], sin_row[1] or 0.0

    if sin_count > 0:
        ranking.append(
            {
                "talent_id": None,
                "name": "Sin talento asignado",
                "category": None,
                "revenue": float(sin_revenue),
                "deal_count": sin_count,
                "is_sin_talento": True,
            }
        )

    return ranking
