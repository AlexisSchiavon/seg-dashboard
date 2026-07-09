"""Data-health checks (Prompt 3, Feature 2).

Read-only detection of operational data problems that are the responsibility of
the Talent Agency team to resolve (they live in Pipedrive/Trello, not in this
system). Each check returns count + affected value + item list with direct links.

All checks are pure reads against the local cache (seg.db). No external calls.
"""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Deal, HealthCheckSnapshot, TrelloCard

logger = logging.getLogger("app.health_checks")

PIPE_URL = "https://talentagency.pipedrive.com/deal/{}"
# The full 24-char Trello card id resolves via redirect to the canonical short URL.
TRELLO_URL = "https://trello.com/c/{}"

# Last Pipedrive funnel stage before Trello takes over (execution/collection).
FINAL_FUNNEL_STAGE = "Contrato"
# Only surface data from this year onward; older data is archived noise.
HISTORY_CUTOFF = "2026-01-01"
OVERDUE_DAYS = 30
# Raise a DATA_HEALTH_ALERT when a check's count grows by more than this fraction.
ALERT_GROWTH = 0.10
MAX_ITEMS = 500  # safety cap per check


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _deal_item(deal: Deal, trello_card_id: str | None = None) -> dict:
    return {
        "id_ref": f"pipedrive:{deal.pipedrive_id}",
        "title": deal.title,
        "value": deal.value or 0.0,
        "link_pipedrive": PIPE_URL.format(deal.pipedrive_id),
        "link_trello": TRELLO_URL.format(trello_card_id) if trello_card_id else None,
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }


def _card_item(card: TrelloCard, deal: Deal | None) -> dict:
    return {
        "id_ref": f"trello:{card.trello_card_id}",
        "title": card.name,
        "value": (deal.value or 0.0) if deal else 0.0,
        "link_pipedrive": PIPE_URL.format(deal.pipedrive_id) if deal else None,
        "link_trello": TRELLO_URL.format(card.trello_card_id),
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }


# --------------------------------------------------------------------------- #
# Individual checks — each returns (count, affected_value, items)              #
# --------------------------------------------------------------------------- #

def _c_deals_sin_atribucion(db: Session):
    rows = (
        db.query(Deal)
        .filter(Deal.status == "won", Deal.talent_id.is_(None),
                Deal.won_time >= HISTORY_CUTOFF)
        .order_by(Deal.value.desc())
        .limit(MAX_ITEMS)
        .all()
    )
    total = db.query(func.count(Deal.id), func.coalesce(func.sum(Deal.value), 0.0)).filter(
        Deal.status == "won", Deal.talent_id.is_(None), Deal.won_time >= HISTORY_CUTOFF
    ).one()
    return total[0], float(total[1]), [_deal_item(d) for d in rows]


def _c_final_funnel_no_won(db: Session):
    q = db.query(Deal).filter(Deal.stage_name == FINAL_FUNNEL_STAGE, Deal.status != "won")
    rows = q.order_by(Deal.value.desc()).limit(MAX_ITEMS).all()
    val = sum(d.value or 0.0 for d in rows)
    return q.count(), float(val), [_deal_item(d) for d in rows]


def _c_won_sin_card(db: Session):
    linked = db.query(TrelloCard.deal_id).filter(TrelloCard.deal_id.isnot(None))
    q = db.query(Deal).filter(Deal.status == "won", Deal.id.notin_(linked))
    rows = q.order_by(Deal.value.desc()).limit(MAX_ITEMS).all()
    val = sum(d.value or 0.0 for d in rows)
    return q.count(), float(val), [_deal_item(d) for d in rows]


def _c_cobrar_sin_due(db: Session):
    rows = (
        db.query(TrelloCard, Deal)
        .outerjoin(Deal, TrelloCard.deal_id == Deal.id)
        .filter(TrelloCard.list_state == "cobranza", TrelloCard.collection_date.is_(None))
        .limit(MAX_ITEMS)
        .all()
    )
    return len(rows), 0.0, [_card_item(c, d) for c, d in rows]


def _c_vencidas_sin_actualizar(db: Session):
    cutoff = date.today() - timedelta(days=OVERDUE_DAYS)
    rows = (
        db.query(TrelloCard, Deal)
        .outerjoin(Deal, TrelloCard.deal_id == Deal.id)
        .filter(TrelloCard.list_state == "cobranza",
                TrelloCard.collection_date.isnot(None),
                TrelloCard.collection_date < cutoff)
        .order_by(TrelloCard.collection_date.asc())
        .limit(MAX_ITEMS)
        .all()
    )
    val = sum((d.value or 0.0) for _, d in rows if d)
    return len(rows), float(val), [_card_item(c, d) for c, d in rows]


def _c_won_valor_cero(db: Session):
    q = db.query(Deal).filter(
        Deal.status == "won",
        ((Deal.value == 0) | (Deal.value.is_(None))),
    )
    rows = q.order_by(Deal.won_time.desc()).limit(MAX_ITEMS).all()
    return q.count(), 0.0, [_deal_item(d) for d in rows]


def _c_collection_pasado(db: Session):
    today = date.today()
    # expected_collection_date is a free-text VARCHAR; parse defensively in Python.
    candidates = (
        db.query(Deal)
        .filter(Deal.status == "open", Deal.expected_collection_date.isnot(None))
        .all()
    )
    items, val, count = [], 0.0, 0
    for d in candidates:
        ecd = _parse_date(d.expected_collection_date)
        if ecd is not None and ecd < today:
            count += 1
            val += d.value or 0.0
            if len(items) < MAX_ITEMS:
                items.append(_deal_item(d))
    return count, float(val), items


# --------------------------------------------------------------------------- #
# Registry                                                                     #
# --------------------------------------------------------------------------- #

CHECKS = [
    {
        "check_id": "DEALS_SIN_ATRIBUCION_TALENTO",
        "human_title": "Deals ganados sin talento asignado",
        "description": ("Deals marcados como ganados en Pipedrive que no tienen un "
                        "talento asignado según el método de atribución activo."),
        "responsibility": "TA", "severity": "alta", "fn": _c_deals_sin_atribucion,
    },
    {
        "check_id": "DEALS_FINAL_FUNNEL_NO_WON",
        "human_title": "Deals en etapa final del funnel sin marcar como ganados",
        "description": (f"Deals en la etapa '{FINAL_FUNNEL_STAGE}' que no están en "
                        "estado ganado."),
        "responsibility": "TA", "severity": "media", "fn": _c_final_funnel_no_won,
    },
    {
        "check_id": "DEALS_WON_SIN_CARD_TRELLO",
        "human_title": "Deals ganados sin tarjeta en Trello",
        "description": "Deals ganados que no tienen una tarjeta de ejecución/cobranza en Trello.",
        "responsibility": "TA", "severity": "media", "fn": _c_won_sin_card,
    },
    {
        "check_id": "CARDS_COBRAR_SIN_DUE_DATE",
        "human_title": "Tarjetas de cobranza sin fecha de cobro",
        "description": "Tarjetas en la columna de cobranza sin fecha de cobro (due).",
        "responsibility": "TA", "severity": "alta", "fn": _c_cobrar_sin_due,
    },
    {
        "check_id": "CARDS_VENCIDAS_SIN_ACTUALIZAR",
        "human_title": "Cobros vencidos sin actualizar",
        "description": f"Tarjetas de cobranza con fecha vencida hace más de {OVERDUE_DAYS} días.",
        "responsibility": "TA", "severity": "alta", "fn": _c_vencidas_sin_actualizar,
    },
    {
        "check_id": "DEALS_WON_VALOR_CERO",
        "human_title": "Deals ganados en $0",
        "description": "Deals ganados con valor 0 o sin valor registrado.",
        "responsibility": "TA", "severity": "media", "fn": _c_won_valor_cero,
    },
    {
        "check_id": "DEALS_COLLECTION_PASADO",
        "human_title": "Deals con fecha de cobro pasada y sin avanzar",
        "description": ("Deals abiertos cuya fecha esperada de cobro ya pasó y siguen "
                        "sin cambiar de estado."),
        "responsibility": "TA", "severity": "media", "fn": _c_collection_pasado,
    },
]
CHECK_BY_ID = {c["check_id"]: c for c in CHECKS}


def _run_one(db: Session, spec: dict) -> dict:
    """Run a single check; on failure return a degraded result (never raises)."""
    meta = {k: spec[k] for k in ("check_id", "human_title", "description",
                                 "responsibility", "severity")}
    try:
        count, value, items = spec["fn"](db)
        meta.update(count=count, affected_value=value, items=items,
                    available=True, detected_at=datetime.now(timezone.utc).isoformat())
    except Exception:  # noqa: BLE001 — one failed check must not break the rest
        logger.exception("health check failed: %s", spec["check_id"])
        meta.update(count=0, affected_value=0.0, items=[], available=False,
                    detected_at=datetime.now(timezone.utc).isoformat())
    return meta


def run_all_checks(db: Session) -> list[dict]:
    """Run every check and return full results (metadata + count + value + items)."""
    return [_run_one(db, spec) for spec in CHECKS]


def get_check_items(db: Session, check_id: str, limit: int = 50, cursor: int = 0):
    """Return (items_page, total, next_cursor) for one check's affected items."""
    spec = CHECK_BY_ID.get(check_id)
    if spec is None:
        return None
    result = _run_one(db, spec)
    items = result["items"]
    limit = max(1, min(int(limit), 200))
    cursor = max(0, int(cursor))
    page = items[cursor:cursor + limit]
    consumed = cursor + len(page)
    next_cursor = consumed if consumed < len(items) else None
    return page, result["count"], next_cursor


def save_snapshots(db: Session, results: list[dict] | None = None) -> list[dict]:
    """Persist a snapshot per check, compute resolved_delta vs the previous
    snapshot, and emit a DATA_HEALTH_ALERT when a count grows beyond ALERT_GROWTH.
    """
    from app.services.audit import log_action

    results = results if results is not None else run_all_checks(db)
    for r in results:
        if not r.get("available", True):
            continue
        prev = (
            db.query(HealthCheckSnapshot)
            .filter(HealthCheckSnapshot.check_id == r["check_id"])
            .order_by(HealthCheckSnapshot.snapshot_at.desc(), HealthCheckSnapshot.id.desc())
            .first()
        )
        prev_count = prev.count if prev else None
        delta = (r["count"] - prev_count) if prev_count is not None else None
        db.add(HealthCheckSnapshot(
            check_id=r["check_id"], count=r["count"],
            affected_value=r["affected_value"], resolved_delta=delta,
        ))
        if prev_count and r["count"] > prev_count * (1 + ALERT_GROWTH):
            log_action(
                "DATA_HEALTH_ALERT", actor="system", entity_type="system",
                entity_id=r["check_id"],
                payload={"check_id": r["check_id"], "before": prev_count,
                         "after": r["count"], "affected_value": r["affected_value"]},
                notes=f"{r['human_title']}: subió de {prev_count} a {r['count']}",
            )
    db.commit()
    return results


def get_latest(db: Session) -> dict:
    """Latest snapshot per check + last-24h trend. Runs+snapshots once if empty."""
    have_any = db.query(HealthCheckSnapshot.id).first() is not None
    if not have_any:
        save_snapshots(db)

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    out = []
    for spec in CHECKS:
        cid = spec["check_id"]
        latest = (
            db.query(HealthCheckSnapshot)
            .filter(HealthCheckSnapshot.check_id == cid)
            .order_by(HealthCheckSnapshot.snapshot_at.desc(), HealthCheckSnapshot.id.desc())
            .first()
        )
        trend_rows = (
            db.query(HealthCheckSnapshot.count)
            .filter(HealthCheckSnapshot.check_id == cid,
                    HealthCheckSnapshot.snapshot_at >= since)
            .order_by(HealthCheckSnapshot.snapshot_at.asc())
            .all()
        )
        out.append({
            "check_id": cid,
            "human_title": spec["human_title"],
            "description": spec["description"],
            "responsibility": spec["responsibility"],
            "severity": spec["severity"],
            "count": latest.count if latest else 0,
            "affected_value": latest.affected_value if latest else 0.0,
            "resolved_delta": latest.resolved_delta if latest else None,
            "trend_24h": [c for (c,) in trend_rows],
            "detected_at": (latest.snapshot_at.isoformat() if latest else None),
        })
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "checks": out}
