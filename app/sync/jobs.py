"""Pipedrive -> SQLite sync job.

`sync_pipedrive(db)` is the single entry point, callable from:
- the manual "Sincronizar ahora" endpoint (app/routers/sync.py)
- the hourly APScheduler job (app/sync/scheduler.py)
- tests (tests/test_sync.py)

Pitfall 3: a DealStageEvent row is only ever written when an EXISTING Deal
row's stage_id/status changes on a subsequent sync. The very first sync of
a deal (INSERT) must not create a stage event.

Pitfall 5: a concurrency guard prevents two syncs running at once. If a
SyncLog with status="running" already exists and is not stale, this
function no-ops and returns that SyncLog unchanged.

Security (T-02-01): on error, persist only `str(exc)` to SyncLog.error_message
-- never log/store full request or response objects (the `x-api-token`
header is a secret).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.integrations import pipedrive
from app.models import Deal, DealStageEvent, SyncLog, TalentProduct

# If a SyncLog has been "running" for longer than this, treat it as stale
# (e.g. the process crashed mid-sync) and allow a new sync to start.
STALE_RUNNING_TIMEOUT = timedelta(hours=1)

COMMISSION_RATE = 0.70


def _is_stale(running: SyncLog) -> bool:
    started_at = running.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - started_at > STALE_RUNNING_TIMEOUT


def sync_pipedrive(db: Session) -> SyncLog:
    """Sync deals from Pipedrive into the local Deal/DealStageEvent tables.

    Returns the SyncLog row for this sync run (or the existing in-flight
    SyncLog if a concurrent sync is already running and not stale).
    """
    # 1. Concurrency guard (Pitfall 5).
    running = (
        db.query(SyncLog)
        .filter(SyncLog.status == "running")
        .order_by(SyncLog.started_at.desc())
        .first()
    )
    if running is not None and not _is_stale(running):
        return running

    # 2. Write SyncLog row immediately so concurrent callers see "running".
    sync_log = SyncLog(
        source="pipedrive",
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db.add(sync_log)
    db.commit()
    db.refresh(sync_log)

    try:
        client = pipedrive._client()

        # 3. Field maps + stage map (stage_id -> name).
        key_by_name, option_labels = pipedrive.build_field_maps(client)
        loss_reason_key = key_by_name.get("Razón de pérdida")
        brand_category_key = key_by_name.get("Categoría de marca")
        expected_collection_date_key = key_by_name.get("Fecha de cobro esperada")

        # PIPE-05's 6-stage funnel is only partially sourced from Pipedrive:
        # Pipedrive pipeline 2 has 4 stages (6 Llamada, 7 Cotizacion,
        # 8 Negociacion, 9 Contrato y factura). "En ejecucion" and "Cobranza"
        # come from Trello (Phase 4), not Pipedrive.
        stage_name_by_id: dict[int, str] = {
            stage["id"]: stage["name"] for stage in pipedrive.get_stages(client)
        }

        # 4. Determine updated_since for incremental sync (omit on first sync).
        last_success = (
            db.query(SyncLog)
            .filter(SyncLog.status == "success")
            .order_by(SyncLog.finished_at.desc())
            .first()
        )
        updated_since = None
        if last_success is not None and last_success.finished_at is not None:
            finished_at = last_success.finished_at
            if finished_at.tzinfo is None:
                finished_at = finished_at.replace(tzinfo=timezone.utc)
            updated_since = finished_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        deals = list(pipedrive.get_deals(client, updated_since=updated_since))

        # 5. Bulk-fetch deal products.
        deal_ids = [d["id"] for d in deals]
        products_by_deal = pipedrive.get_deal_products_bulk(client, deal_ids)

        # Map pipedrive_product_id -> talent_id (PIPE-02 / D-17).
        talent_id_by_product_id: dict[int, int] = {
            tp.pipedrive_product_id: tp.talent_id
            for tp in db.query(TalentProduct).all()
            if tp.pipedrive_product_id is not None
        }

        records_synced = 0
        for deal in deals:
            pipedrive_id = deal["id"]
            value = float(deal.get("value") or 0)
            stage_id = deal["stage_id"]
            stage_name = stage_name_by_id.get(stage_id, "")
            status = deal["status"]

            # 6. Talent resolution via first product's pipedrive_product_id.
            talent_id = None
            for product in products_by_deal.get(pipedrive_id, []):
                product_id = product.get("product_id")
                if product_id in talent_id_by_product_id:
                    talent_id = talent_id_by_product_id[product_id]
                    break

            commission_amount = value * COMMISSION_RATE
            is_sin_cotizar = value == 0

            loss_reason = (
                pipedrive.resolve_custom_field(deal, loss_reason_key, option_labels)
                if loss_reason_key
                else None
            )
            brand_category = (
                pipedrive.resolve_custom_field(deal, brand_category_key, option_labels)
                if brand_category_key
                else None
            )
            expected_collection_date = (
                pipedrive.resolve_custom_field(deal, expected_collection_date_key, option_labels)
                if expected_collection_date_key
                else None
            )

            existing_deal = db.query(Deal).filter(Deal.pipedrive_id == pipedrive_id).first()

            # 7. Diff stage_id/status vs existing row -> DealStageEvent (Pitfall 3).
            stage_entered_at = existing_deal.stage_entered_at if existing_deal else None
            if existing_deal is not None and (
                existing_deal.stage_id != stage_id or existing_deal.status != status
            ):
                db.add(
                    DealStageEvent(
                        deal_pipedrive_id=pipedrive_id,
                        talent_id=talent_id,
                        from_stage=existing_deal.stage_name,
                        to_stage=stage_name,
                        from_status=existing_deal.status,
                        to_status=status,
                    )
                )
                stage_entered_at = datetime.now(timezone.utc)
            elif existing_deal is None:
                stage_entered_at = datetime.now(timezone.utc)

            # 8. Upsert Deal.
            if existing_deal is None:
                existing_deal = Deal(pipedrive_id=pipedrive_id)
                db.add(existing_deal)

            existing_deal.title = deal.get("title", "")
            existing_deal.value = value
            existing_deal.currency = deal.get("currency", "MXN")
            existing_deal.stage_id = stage_id
            existing_deal.stage_name = stage_name
            existing_deal.status = status
            existing_deal.talent_id = talent_id
            existing_deal.commission_amount = commission_amount
            existing_deal.is_sin_cotizar = is_sin_cotizar
            existing_deal.loss_reason = loss_reason
            existing_deal.brand_category = brand_category
            existing_deal.expected_collection_date = expected_collection_date
            existing_deal.stage_entered_at = stage_entered_at
            existing_deal.update_time = deal.get("update_time", "")
            existing_deal.add_time = deal.get("add_time")

            records_synced += 1

        # 9. Commit deal upserts + stage events.
        db.commit()

        # 10. Mark sync success.
        sync_log.status = "success"
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.records_synced = records_synced
        db.commit()
        db.refresh(sync_log)

    except Exception as exc:  # noqa: BLE001 - persist error, never re-raise raw request/response
        db.rollback()
        sync_log.status = "error"
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.error_message = str(exc)
        db.commit()
        db.refresh(sync_log)

    return sync_log
