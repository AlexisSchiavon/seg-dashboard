"""Global KPI aggregation and talent ranking service.

Functions take db: Session as the first parameter — Depends() wiring belongs
in app/routers/dashboard.py, not here (02-PATTERNS.md convention).

Pitfall 4 (global vs per-talent split):
  - Global KPIs: query Deal directly, NO join to Talent — talent_id IS NULL
    rows are included in totals.
  - Ranking: outerjoin Talent←Deal to aggregate per talent, PLUS a separate
    query for the Sin-talento bucket (Deal.talent_id.is_(None)) appended last.
"""

from datetime import date, datetime, timedelta

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


def talent_detail(
    db: Session,
    talent_id: int,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    """Return per-talent KPIs, lost opportunities, and brand-category breakdown.

    Fase 7 (D4): when (start, end) are given, the *closed* metrics are scoped to
    that period — Cerrados/Comisión by won_time, the lost donut by update_time.
    The *active* metrics (Pipeline open, funnel, brand mix) stay all-time
    snapshots ("estado vivo del negocio" — Luis never asks "how big was my
    pipeline in March?"). start/end default to None = all-time (back-compat for
    existing callers / direct tests); the endpoint layer resolves the D2
    current-month default and always passes explicit bounds.

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

    # Cerrados/Comisión — won deals (D4: filtered by won_time when a period is set).
    # 7.4: reuse deals_won_in_period (the canonical won-in-range query) instead of
    # duplicating the date filter here.
    if start is not None and end is not None:
        won = deals_won_in_period(db, start.isoformat(), end.isoformat(), talent_id)
        won_count, won_value, commission = won["count"], won["total_value"], won["total_commission"]
    else:
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

    # 4. Lost opportunities (D-25). Fase 7/P1: filter by loss date when a period
    # is set. No close_time/lost_time column exists, so update_time is the proxy
    # (it is the last Pipedrive touch — for a lost deal, approximately when it was
    # marked lost). update_time is stored as an ISO-8601 *string*
    # ("2026-06-20T23:30:00"), so a lexicographic range over [start, day-after-end)
    # selects the correct calendar window: fixed-width ISO strings sort in the same
    # order as the instants they encode. Documented as an approximation, not exact.
    lost_query = db.query(Deal).filter(Deal.talent_id == talent_id, Deal.status == "lost")
    if start is not None and end is not None:
        start_str = start.isoformat()
        end_exclusive_str = (end + timedelta(days=1)).isoformat()
        lost_query = lost_query.filter(
            Deal.update_time >= start_str,
            Deal.update_time < end_exclusive_str,
        )
    lost_deals = lost_query.all()

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


def deals_won_in_period(
    db: Session,
    start_date: str,
    end_date: str,
    talent_id: int | None = None,
) -> dict:
    """Return deals signed (status='won') whose won_time falls in [start, end].

    5.4 (D3): the agent uses this for date-range questions like "¿qué se firmó
    en junio 2026?". "Firmado/ganado/cerrado" = status='won' (5.1/D1), and the
    date filter is on won_time (NOT add_time/update_time) — see 5.3.

    Args:
      start_date, end_date: inclusive 'YYYY-MM-DD' bounds (UTC). end_date is
        inclusive of the whole day.
      talent_id: optional filter to a single talent.

    Returns a dict: {start_date, end_date, count, total_value, deals:[...]}.
    Won deals with a NULL won_time are excluded (cannot be placed in a period).
    Raises ValueError if a date string is not 'YYYY-MM-DD'.
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        # Inclusive end: everything strictly before the next day's midnight.
        end_exclusive = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    except ValueError as exc:
        raise ValueError("start_date and end_date must be 'YYYY-MM-DD'") from exc

    # won_time round-trips naive UTC from SQLite, so compare against naive bounds.
    query = (
        db.query(Deal)
        .filter(
            Deal.status == "won",
            Deal.won_time.isnot(None),
            Deal.won_time >= start,
            Deal.won_time < end_exclusive,
        )
    )
    if talent_id is not None:
        query = query.filter(Deal.talent_id == talent_id)

    deals = query.order_by(Deal.won_time).all()

    talent_ids = {d.talent_id for d in deals if d.talent_id is not None}
    talent_names: dict[int, str] = {}
    if talent_ids:
        for t in db.query(Talent.id, Talent.name).filter(Talent.id.in_(talent_ids)).all():
            talent_names[t[0]] = t[1]

    deal_list = [
        {
            "title": d.title,
            "value": float(d.value),
            "talent_name": talent_names.get(d.talent_id, "Sin talento asignado"),
            "won_time": d.won_time.isoformat() if d.won_time else None,
        }
        for d in deals
    ]

    return {
        "start_date": start_date,
        "end_date": end_date,
        "count": len(deal_list),
        "total_value": float(sum(d["value"] for d in deal_list)),
        # 7.4: total_commission lets talent_detail reuse this for the Comisión KPI
        # without a second won-in-period query (no duplicated date-filter logic).
        "total_commission": float(sum(d.commission_amount or 0.0 for d in deals)),
        "deals": deal_list,
    }


def flujo_dinero_kpis(
    db: Session,
    talent_id: int,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    """Return the 3 money-flow KPI tiles for the Por Talento Flujo de dinero view.

    Tiles:
      - Campañas firmadas (blue): won deals (status='won') — count + total value.
        5.1 (D1): "firmado" = "ganado" = status='won' ONLY. The "Contrato" stage
        means a deal is in the signing process — NOT yet signed/won (Luis, 25-jun).
        Fase 7/D4: filtered by won_time when (start, end) are set.
      - Cobrado (green): deals linked to a TrelloCard with list_state="cerrado".
        Fase 7/D4: filtered by the card's collection_date when a period is set.
      - Pendiente por cobrar (amber): max(0, firmadas - cobrado) — never negative.
        Fase 7/D4: this is a *state* ("ganados aún no cobrados"), NOT a period — it
        is ALWAYS computed from all-time figures, independent of the selected
        period, so it does not silently drop receivables signed before the period.

    start/end default to None = all-time (back-compat for direct callers/tests).
    """
    from app.models import TrelloCard

    # Pendiente is a state (D4) — always all-time, regardless of the period filter.
    alltime_firmadas_value = db.query(
        func.coalesce(func.sum(Deal.value), 0.0),
    ).filter(Deal.talent_id == talent_id, Deal.status == "won").scalar() or 0.0
    alltime_cobrado_value = db.query(
        func.coalesce(func.sum(Deal.value), 0.0),
    ).join(TrelloCard, TrelloCard.deal_id == Deal.id).filter(
        Deal.talent_id == talent_id,
        TrelloCard.list_state == "cerrado",
    ).scalar() or 0.0
    pendiente_value = max(0.0, float(alltime_firmadas_value) - float(alltime_cobrado_value))

    # Campañas firmadas tile — won deals (D4: by won_time within the period).
    # 7.4: reuse deals_won_in_period rather than re-deriving the won-in-range query.
    if start is not None and end is not None:
        won = deals_won_in_period(db, start.isoformat(), end.isoformat(), talent_id)
        firmadas_count, firmadas_value = won["count"], won["total_value"]
    else:
        firmadas_row = db.query(
            func.count(Deal.id),
            func.coalesce(func.sum(Deal.value), 0.0),
        ).filter(Deal.talent_id == talent_id, Deal.status == "won").one()
        firmadas_count, firmadas_value = firmadas_row[0], firmadas_row[1] or 0.0

    # Cobrado tile — cerrado cards (D4: by collection_date within the period).
    cobrado_query = db.query(
        func.coalesce(func.sum(Deal.value), 0.0),
    ).join(TrelloCard, TrelloCard.deal_id == Deal.id).filter(
        Deal.talent_id == talent_id,
        TrelloCard.list_state == "cerrado",
    )
    if start is not None and end is not None:
        # collection_date is a Date column → compare directly (inclusive bounds).
        cobrado_query = cobrado_query.filter(
            TrelloCard.collection_date >= start,
            TrelloCard.collection_date <= end,
        )
    cobrado_value = cobrado_query.scalar() or 0.0

    return {
        "kpis": [
            {
                "label": "Campañas firmadas",
                "value": float(firmadas_value),
                "count": firmadas_count,
                "variant": "blue",
            },
            {
                "label": "Cobrado",
                "value": float(cobrado_value),
                "count": None,
                "variant": "green",
            },
            {
                "label": "Pendiente por cobrar",
                "value": pendiente_value,
                "count": None,
                "variant": "amber",
            },
        ]
    }


# =============================================================================
# Fase 9.7 — Talent-facing figures (audience = talent, not TA-internal).
# All amounts are the talent's 70% share (Deal.commission_amount, verified to
# equal value*0.70). These helpers expose ONLY talent-appropriate numbers —
# never pipeline, TA commission, or funnel internals.
# =============================================================================


def _talent_70(deal: Deal) -> float:
    """The talent's 70% share for a deal: commission_amount, or value*0.70 fallback."""
    if deal.commission_amount is not None:
        return float(deal.commission_amount)
    return float(deal.value or 0.0) * 0.70


def compute_talent_facing_kpis(
    db: Session, talent_id: int, start: date, end: date
) -> dict:
    """The 3 talent-facing headline KPIs for the period, all in the talent's 70%.

      - firmadas: count of won deals (won_time in period) + their 70% value.
      - cobrado:  70% of deals whose 'cerrado' card collection_date is in the period.
      - por_cobrar: max(0, firmadas_70 - cobrado_70)  (D-9.7: month-scoped).

    Returns {firmadas_count, firmadas_70, cobrado_70, por_cobrar_70}.
    """
    from app.models import TrelloCard

    # Firmadas — won in period. 70% = total_commission (sum of commission_amount).
    won = deals_won_in_period(db, start.isoformat(), end.isoformat(), talent_id)
    firmadas_count = won["count"]
    firmadas_70 = float(won["total_commission"])

    # Cobrado — cerrado cards whose collection_date falls in the period, 70% share.
    cobrado_70 = (
        db.query(func.coalesce(func.sum(Deal.commission_amount), 0.0))
        .join(TrelloCard, TrelloCard.deal_id == Deal.id)
        .filter(
            Deal.talent_id == talent_id,
            TrelloCard.list_state == "cerrado",
            TrelloCard.collection_date >= start,
            TrelloCard.collection_date <= end,
        )
        .scalar()
    ) or 0.0
    cobrado_70 = float(cobrado_70)

    return {
        "firmadas_count": int(firmadas_count),
        "firmadas_70": firmadas_70,
        "cobrado_70": cobrado_70,
        "por_cobrar_70": max(0.0, firmadas_70 - cobrado_70),
    }


def account_status_breakdown(
    db: Session, talent_id: int, year: int | None = None
) -> dict:
    """The 'Estado de tus cuentas' widget buckets, all in the talent's 70%.

      - proximos_meses: ejecucion/cobranza cards whose resolved collection_date is
        today or later (money still to come, any future month).
      - retraso: ejecucion/cobranza cards whose resolved collection_date is in the
        past. D-9.7 sanitisation: cards with an explicit collection_date EARLIER
        than the deal's add_time (impossible dates) are EXCLUDED as data garbage.
      - cobrado_ano: 'cerrado' cards with collection_date in the given calendar
        year (defaults to the current year).

    Returns {proximos_meses:{count,value70}, retraso:{count,value70},
             cobrado_ano:{count,value70}}.
    """
    from app.models import TrelloCard
    from app.services.trello_service import resolve_collection_date

    today = date.today()
    year = year or today.year

    rows = (
        db.query(TrelloCard, Deal)
        .join(Deal, TrelloCard.deal_id == Deal.id)
        .filter(Deal.talent_id == talent_id)
        .all()
    )

    proximos = {"count": 0, "value70": 0.0}
    retraso = {"count": 0, "value70": 0.0}
    cobrado_ano = {"count": 0, "value70": 0.0}

    for card, deal in rows:
        share = _talent_70(deal)
        if card.list_state in ("ejecucion", "cobranza"):
            resolved = card.collection_date or resolve_collection_date(None, deal)
            if resolved >= today:
                proximos["count"] += 1
                proximos["value70"] += share
            else:
                # Sanitise: skip impossible dates (collection before the deal existed).
                add_dt = None
                if deal.add_time:
                    try:
                        add_dt = date.fromisoformat(deal.add_time[:10])
                    except ValueError:
                        add_dt = None
                if card.collection_date and add_dt and card.collection_date < add_dt:
                    continue  # data garbage — excluded from retraso (D-9.7)
                retraso["count"] += 1
                retraso["value70"] += share
        elif card.list_state == "cerrado":
            cd = card.collection_date
            if cd is not None and cd.year == year:
                cobrado_ano["count"] += 1
                cobrado_ano["value70"] += share

    return {
        "proximos_meses": proximos,
        "retraso": retraso,
        "cobrado_ano": cobrado_ano,
    }
