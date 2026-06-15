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
from app.services.funnel import talent_funnel


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


def talent_detail(db: Session, talent_id: int) -> dict:
    """Return per-talent KPIs, lost opportunities, and brand-category breakdown.

    Per-talent figures exclude talent_id IS NULL deals (Pitfall 4).
    loss_reason is read directly as a resolved Spanish label (Plan 02-01 — Pitfall 2).

    Returns a dict matching the TalentDetail schema shape:
      {
        talent_id: int,
        name: str,
        category: str | None,
        kpis: list[KpiTile],
        funnel: list[StageBucket],
        lost_summary: list[LostReasonSummary],
        lost_opportunities: list[LostOpportunity],
        brand_categories: list[BrandCategorySlice],
      }
    """
    # 1. Look up the talent row for name/category
    talent = db.get(Talent, talent_id)
    if talent is None:
        raise ValueError(f"Talent {talent_id} not found")

    # 2. Per-talent KPIs (filter by talent_id only — Pitfall 4: no NULL inclusion)
    # Pipeline = open deals only. Lost deals are shown separately in
    # lost_opportunities; including them here inflated the "Pipeline" label
    # with deals already out of play (WR-05).
    pipeline_row = db.query(
        func.coalesce(func.sum(Deal.value), 0.0),
    ).filter(Deal.talent_id == talent_id, Deal.status == "open").scalar() or 0.0

    won_row = db.query(
        func.count(Deal.id),
        func.coalesce(func.sum(Deal.value), 0.0),
        func.coalesce(func.sum(Deal.commission_amount), 0.0),
    ).filter(Deal.talent_id == talent_id, Deal.status == "won").one()
    won_count, won_value, commission = won_row[0], won_row[1] or 0.0, won_row[2] or 0.0

    kpis = [
        {"label": "Pipeline", "value": float(pipeline_row), "count": None, "variant": "accent"},
        {"label": "Cerrados", "value": float(won_value), "count": won_count, "variant": "purple"},
        {"label": "Comisión", "value": float(commission), "count": None, "variant": "green"},
    ]

    # 3. Per-talent funnel (reuses shared STAGES constant via funnel.py)
    funnel_stages = talent_funnel(db, talent_id)

    # 4. Lost opportunities (D-25)
    lost_deals = (
        db.query(Deal)
        .filter(Deal.talent_id == talent_id, Deal.status == "lost")
        .all()
    )

    # Build per-reason summary (group by the resolved Spanish label — never re-resolve integers)
    reason_counts: dict[str, int] = {}
    for deal in lost_deals:
        reason = deal.loss_reason or "Sin razón"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    lost_summary = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1])
    ]

    lost_opportunities = [
        {
            "title": deal.title,
            "amount": float(deal.value),
            "loss_reason": deal.loss_reason,  # Already a resolved Spanish label (Pitfall 2)
        }
        for deal in lost_deals
    ]

    # 5. Brand categories (D-26/D-27): % by DEAL COUNT, not revenue
    brand_rows = (
        db.query(Deal.brand_category, func.count(Deal.id))
        .filter(Deal.talent_id == talent_id, Deal.brand_category.isnot(None))
        .group_by(Deal.brand_category)
        .all()
    )

    total_categorized = sum(row[1] for row in brand_rows)
    brand_categories = []
    if total_categorized > 0:
        for row in sorted(brand_rows, key=lambda x: -x[1]):
            pct = (row[1] / total_categorized) * 100
            brand_categories.append({
                "category": row[0],
                "count": row[1],
                "pct": round(pct, 2),
            })

    return {
        "talent_id": talent_id,
        "name": talent.name,
        "category": talent.category,
        "kpis": kpis,
        "funnel": funnel_stages,
        "lost_summary": lost_summary,
        "lost_opportunities": lost_opportunities,
        "brand_categories": brand_categories,
    }
