"""Funnel aggregation, bottleneck detection, and activity feed service.

Functions take db: Session as first parameter — Depends() belongs in the router.

PIPE-05 canonical stage order (6 stages):
  Llamada → Cotización → Negociación → Contrato → En ejecución → Cobranza

"En ejecución" and "Cobranza" have no Pipedrive data source until Phase 4
(Trello); they are always emitted with count=0, amount=0.0 until then.
"""

from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Deal, DealStageEvent, Talent

# PIPE-05: canonical 6-stage order — do NOT reorder or remove
STAGES = [
    "Llamada",
    "Cotización",
    "Negociación",
    "Contrato",
    "En ejecución",
    "Cobranza",
]

# Minimum deal count for bottleneck detection (RESEARCH.md Pattern 4)
BOTTLENECK_MIN_SAMPLE = 10


def funnel_overview(db: Session) -> dict:
    """Return the 6-stage funnel with counts/amounts and bottleneck info.

    Returns a dict matching the FunnelOverview schema shape:
      {
        stages: list[StageBucket],
        bottleneck: BottleneckInfo | None,
        insufficient_data: bool,
        has_data: bool,
      }

    Bottleneck heuristic (RESEARCH.md Pattern 4):
    For each adjacent stage pair (i, i+1), compute:
      conversion_i = count(open deals at stage >= i+1) / count(deals at stage >= i)
    Flag the pair with the lowest conversion_i. If total deals < 10, set
    insufficient_data=True and bottleneck=None.
    """
    # Build a dict of stage_name -> (count, amount) for OPEN deals only
    rows = (
        db.query(
            Deal.stage_name,
            func.count(Deal.id),
            func.coalesce(func.sum(Deal.value), 0.0),
        )
        .filter(Deal.status == "open")
        .group_by(Deal.stage_name)
        .all()
    )

    stage_map: dict[str, tuple[int, float]] = {}
    for row in rows:
        stage_map[row[0]] = (row[1], float(row[2]))

    # Build ordered stage buckets — always emit all 6, even with 0 count
    stages = []
    for stage in STAGES:
        count, amount = stage_map.get(stage, (0, 0.0))
        stages.append({"stage": stage, "count": count, "amount": amount})

    # Total deal count (all statuses) for sample-size check
    total_deals = db.query(func.count(Deal.id)).scalar() or 0

    has_data = total_deals > 0

    # Bottleneck detection (RESEARCH.md Pattern 4)
    if total_deals < BOTTLENECK_MIN_SAMPLE:
        return {
            "stages": stages,
            "bottleneck": None,
            "insufficient_data": True,
            "has_data": has_data,
        }

    # For each stage pair compute snapshot-ratio conversion
    # conversion_i = deals_at_or_after(stage i+1) / deals_at_or_after(stage i)
    # "At or after" means stage index >= i in the STAGES list.
    #
    # We use all statuses (open+won+lost) for the denominator to reflect the
    # full funnel population that ever reached each stage.

    # Build a per-stage deal count dict (all statuses, by stage_name)
    all_rows = (
        db.query(Deal.stage_name, func.count(Deal.id))
        .group_by(Deal.stage_name)
        .all()
    )
    all_stage_counts: dict[str, int] = {r[0]: r[1] for r in all_rows}

    # Cumulative counts: deals_at_or_after[i] = sum of counts for stages i..5
    cumulative = []
    for i, stage in enumerate(STAGES):
        count_from_here = sum(
            all_stage_counts.get(STAGES[j], 0) for j in range(i, len(STAGES))
        )
        cumulative.append(count_from_here)

    # Find the pair (i, i+1) with the lowest conversion ratio
    min_conversion = None
    min_pair = None

    for i in range(len(STAGES) - 1):
        denom = cumulative[i]
        numer = cumulative[i + 1]
        if denom == 0:
            continue
        conversion = numer / denom
        if min_conversion is None or conversion < min_conversion:
            min_conversion = conversion
            min_pair = (STAGES[i], STAGES[i + 1])

    if min_pair is None or min_conversion is None:
        return {
            "stages": stages,
            "bottleneck": None,
            "insufficient_data": True,
            "has_data": has_data,
        }

    bottleneck = {
        "stage_a": min_pair[0],
        "stage_b": min_pair[1],
        "conversion_pct": round(min_conversion * 100, 1),
    }

    return {
        "stages": stages,
        "bottleneck": bottleneck,
        "insufficient_data": False,
        "has_data": has_data,
    }


def talent_funnel(db: Session, talent_id: int) -> list[dict]:
    """Return the 6-stage funnel for a specific talent's open deals only.

    Reuses the shared STAGES constant — does NOT redefine it.
    Returns a list of StageBucket-shaped dicts for only that talent's deals.
    Bottleneck and insufficient_data are not computed here (that's a global metric).
    """
    rows = (
        db.query(
            Deal.stage_name,
            func.count(Deal.id),
            func.coalesce(func.sum(Deal.value), 0.0),
        )
        .filter(Deal.status == "open", Deal.talent_id == talent_id)
        .group_by(Deal.stage_name)
        .all()
    )

    stage_map: dict[str, tuple[int, float]] = {}
    for row in rows:
        stage_map[row[0]] = (row[1], float(row[2]))

    # Always emit all 6 stages, even with 0 count (same invariant as funnel_overview)
    stages = []
    for stage in STAGES:
        count, amount = stage_map.get(stage, (0, 0.0))
        stages.append({"stage": stage, "count": count, "amount": amount})

    return stages


def recent_activity(db: Session, limit: int = 20) -> list[dict]:
    """Return the most recent DealStageEvents ordered by detected_at desc.

    Looks up Deal title and Talent name for each event.
    talent_name is "Sin talento" when talent_id is None.
    """
    events = (
        db.query(DealStageEvent)
        .order_by(DealStageEvent.detected_at.desc())
        .limit(limit)
        .all()
    )

    # Build a lookup map of pipedrive_id -> Deal to avoid N+1 queries
    deal_ids = list({e.deal_pipedrive_id for e in events})
    if not deal_ids:
        return []

    deals = db.query(Deal).filter(Deal.pipedrive_id.in_(deal_ids)).all()
    deal_map = {d.pipedrive_id: d for d in deals}

    # Build a lookup map of talent_id -> Talent
    talent_ids = list({e.talent_id for e in events if e.talent_id is not None})
    talent_map: dict[int, Talent] = {}
    if talent_ids:
        talents = db.query(Talent).filter(Talent.id.in_(talent_ids)).all()
        talent_map = {t.id: t for t in talents}

    result = []
    for event in events:
        deal = deal_map.get(event.deal_pipedrive_id)
        title = deal.title if deal else f"Deal {event.deal_pipedrive_id}"

        if event.talent_id is not None:
            talent = talent_map.get(event.talent_id)
            talent_name = talent.name if talent else "Sin talento"
        else:
            talent_name = "Sin talento"

        result.append(
            {
                "title": title,
                "to_stage": event.to_stage,
                "talent_name": talent_name,
                "detected_at": event.detected_at,
            }
        )

    return result
