"""Targeted, one-off backfill of Trello cards for an EXPLICIT, manually-approved
list of Pipedrive deal IDs.

Run this in the EasyPanel PROD console AFTER deploy, e.g.:

    # dry-run (default) — prints exactly what it would create, creates nothing:
    python -m app.scripts.backfill_trello_cards --ids 488,519,526

    # actually create (requires TRELLO_AUTO_CREATE_ENABLED=true in env):
    python -m app.scripts.backfill_trello_cards --ids 488,519,526 --confirm

Design (per Fase D decisions):
  - Operates ONLY on the ids passed via --ids (human-approved list).
  - IGNORES the automatic date floor (TRELLO_AUTOCREATE_MIN_WON_DATE) and the
    local trello_cards registry check — the latter is known to be contaminated by
    fuzzy-match mislinks (e.g. pid=91's card wrongly linked to pid=526).
  - KEEPS the live-Trello [seg:deal_id=N] marker check, so running twice never
    duplicates.
  - Respects the create_card whitelist + TRELLO_AUTO_CREATE_ENABLED flag (guards
    live inside create_card).
  - Talent comes from the DB where it runs (talent_id → talent name; NULL →
    "Sin talento asignado"). No per-id hardcodes.
  - Emits a TRELLO_CARD_CREATED audit event per created card.
"""
import argparse
from typing import Callable

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.integrations import trello
from app.models import AuditLog, Deal, Talent, TrelloCard
from app.services import trello_service
from app.services.audit import log_action


def run_backfill(
    db: Session,
    client: httpx.Client,
    pipedrive_ids: list[int],
    confirm: bool,
    out: Callable[[str], None] = print,
) -> dict[str, list[int]]:
    """Create Contrato cards for the given pipedrive_ids. Returns a summary dict
    with keys: created, skipped_existing, skipped_missing."""
    target_list_id = (settings.TRELLO_AUTOCREATE_LIST_ID or "").strip() or trello.CONTRATO_LIST_ID

    # Idempotency, consistent with the reconciliation:
    #  1. FACT: this system already created a card for the deal (audit_log).
    #  2. Live [seg:deal_id] marker present in the target list.
    created_pipedrive_ids: set[int] = {
        int(row[0])
        for row in db.query(AuditLog.entity_id)
        .filter(AuditLog.action_type == "TRELLO_CARD_CREATED", AuditLog.entity_id.isnot(None))
        .all()
        if str(row[0]).isdigit()
    }
    live_marker_ids = trello.list_marker_pipedrive_ids(client, target_list_id)

    talent_names = {t.id: t.name for t in db.query(Talent).all()}

    summary: dict[str, list[int]] = {"created": [], "skipped_existing": [], "skipped_missing": []}
    mode = "CREATE" if confirm else "DRY-RUN"
    out(f"=== Backfill {mode} — target list {target_list_id} — ids={pipedrive_ids} ===")

    for pid in pipedrive_ids:
        deal = db.query(Deal).filter(Deal.pipedrive_id == pid).first()
        if deal is None:
            out(f"[skip] pid={pid}: no existe en la DB — omitido")
            summary["skipped_missing"].append(pid)
            continue
        if pid in created_pipedrive_ids:
            out(f"[skip] pid={pid}: el sistema ya creó una card antes (audit_log) — no recrear")
            summary["skipped_existing"].append(pid)
            continue
        if pid in live_marker_ids:
            out(f"[skip] pid={pid}: ya existe card con marcador [seg:deal_id={pid}] en Trello")
            summary["skipped_existing"].append(pid)
            continue

        talent_name = talent_names.get(deal.talent_id) if deal.talent_id else None
        desc = trello_service.build_auto_card_desc(deal, talent_name, settings.PIPEDRIVE_DOMAIN)

        out(f"\n--- pid={pid} ---")
        out(f"  título       : {deal.title}")
        out(f"  talento      : {talent_name or 'Sin talento asignado'}")
        out(f"  lista destino: {target_list_id}")
        out(f"  descripción  :\n{desc}")

        if not confirm:
            out("  [DRY-RUN] no se crea (usa --confirm para crear)")
            continue

        response = trello.create_card(client, target_list_id, deal.title, desc=desc)
        card_id = response.get("id")
        if card_id is None:
            out(f"  [error] respuesta de Trello sin id — no se registró pid={pid}")
            continue

        collection_date = trello_service.resolve_collection_date(response.get("due"), deal)
        db.add(TrelloCard(
            trello_card_id=card_id,
            name=deal.title,
            list_id=target_list_id,
            list_name="Contrato",
            list_state="ejecucion",
            deal_id=deal.id,
            pipedrive_deal_id_desc=deal.pipedrive_id,
            collection_date=collection_date,
        ))
        live_marker_ids.add(pid)  # guard the rest of this run
        log_action(
            "TRELLO_CARD_CREATED",
            actor="backfill-script",
            entity_type="deal",
            entity_id=deal.pipedrive_id,
            payload={
                "trello_card_id": card_id,
                "list_id": target_list_id,
                "title": deal.title,
                "value": deal.value,
                "backfill": True,
            },
            db=db,
        )
        db.commit()
        summary["created"].append(pid)
        out(f"  [creada] card_id={card_id} url={response.get('shortUrl')}")

    out(
        f"\n=== Resumen: creadas={summary['created']} "
        f"ya_existían={summary['skipped_existing']} "
        f"no_encontradas={summary['skipped_missing']} ==="
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Trello cards for approved deal ids.")
    parser.add_argument("--ids", required=True, help="comma-separated pipedrive_ids, e.g. 488,519,526")
    parser.add_argument("--confirm", action="store_true", help="actually create (default: dry-run)")
    args = parser.parse_args()

    pipedrive_ids = [int(x) for x in args.ids.split(",") if x.strip()]
    db = SessionLocal()
    client = trello._client()
    try:
        run_backfill(db, client, pipedrive_ids, confirm=args.confirm)
    finally:
        client.close()
        db.close()


if __name__ == "__main__":
    main()
