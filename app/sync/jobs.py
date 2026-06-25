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

from app.integrations import pipedrive, sheets, trello
from app.models import Deal, DealStageEvent, Lead, SyncLog, Talent, TalentProduct, TrelloCard
from app.services import trello_service

# If a SyncLog has been "running" for longer than this, treat it as stale
# (e.g. the process crashed mid-sync) and allow a new sync to start.
STALE_RUNNING_TIMEOUT = timedelta(hours=1)

# DECISIÓN PERMANENTE: este flag debe permanecer en False indefinidamente.
# La creación de tarjetas en Trello cuando un deal llega a "Contrato y factura"
# ya la maneja el sistema de Fase 2 Talent que corre en producción. El SEG
# Dashboard es SOLO LECTURA para Trello y Pipedrive — únicamente sincroniza
# el estado de tarjetas existentes, nunca las crea.
TRELLO_AUTO_CREATE_ENABLED = False

COMMISSION_RATE = 0.70


def _parse_pipedrive_datetime(value: str | None) -> datetime | None:
    """Parse a Pipedrive timestamp into a timezone-aware UTC datetime.

    Pipedrive v2 returns ISO 8601 like "2026-06-15T10:30:00Z"; older/v1-shaped
    payloads may use a space separator ("2026-06-15 10:30:00"). Returns None for
    empty/unparseable values. Naive results are assumed UTC (Pipedrive sends UTC).
    """
    if not value:
        return None
    text = value.strip()
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


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
    # 1. Concurrency guard — filter by source so Trello/Sheets syncs don't block Pipedrive.
    running = (
        db.query(SyncLog)
        .filter(SyncLog.source == "pipedrive", SyncLog.status == "running")
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
        brand_category_key = key_by_name.get("Categoría de marca")
        expected_collection_date_key = key_by_name.get("Fecha de cobro esperada")

        # PIPE-05's 6-stage funnel is only partially sourced from Pipedrive:
        # Pipedrive pipeline 2 has 4 stages (6 Llamada, 7 Cotizacion,
        # 8 Negociacion, 9 Contrato y factura). "En ejecucion" and "Cobranza"
        # come from Trello (Phase 4), not Pipedrive.
        #
        # Normalize: strip whitespace (live API returns "Negociación " with a
        # trailing space) and map Pipedrive's verbose label to the canonical
        # STAGES name used by services/funnel.py ("Contrato y factura" → "Contrato").
        _STAGE_CANONICAL = {"Contrato y factura": "Contrato"}
        stage_name_by_id: dict[int, str] = {
            stage["id"]: _STAGE_CANONICAL.get(
                stage["name"].strip(), stage["name"].strip()
            )
            for stage in pipedrive.get_stages(client)
        }

        # 4. Determine updated_since for incremental sync (omit on first sync).
        last_success = (
            db.query(SyncLog)
            .filter(SyncLog.status == "success", SyncLog.source == "pipedrive")
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

            loss_reason = deal.get("lost_reason") or None
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
            # 5.3: persist Pipedrive v2 won_time (UTC) for status='won' deals.
            existing_deal.won_time = _parse_pipedrive_datetime(deal.get("won_time"))

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


def _parse_fecha(raw: str) -> "datetime | None":
    """Parse Fecha_Recepcion from Sheet. Two observed variants:
      - '2026-03-30T17:39:37Z'      (no milliseconds)
      - '2026-03-30T17:45:02.000Z'  (with milliseconds)
    Python 3.12 fromisoformat handles Z natively; .replace() is defensive belt-and-suspenders.
    Returns None for empty string or unparseable values.
    """
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def sync_sheets(db: Session) -> SyncLog:
    """Sync leads from Google Sheets into the local Lead table.

    Upserts by sheet_row_id (natural key under append-only assumption A1).
    Second run with identical rows inserts zero new Lead rows (idempotent).

    Concurrency guard filters by source='sheets' so a running pipedrive sync
    does NOT block this function (Pitfall 6 — source filter is mandatory).

    Security (T-03-01): on error, persist only str(exc) to SyncLog.error_message
    — never log gspread client/worksheet/response objects (may reflect SA credentials).
    """
    # 1. Concurrency guard — filter by source='sheets' only (Pitfall 6).
    running = (
        db.query(SyncLog)
        .filter(SyncLog.source == "sheets", SyncLog.status == "running")
        .order_by(SyncLog.started_at.desc())
        .first()
    )
    if running is not None and not _is_stale(running):
        return running

    # 2. Write SyncLog row immediately so concurrent callers see "running".
    sync_log = SyncLog(
        source="sheets",
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db.add(sync_log)
    db.commit()
    db.refresh(sync_log)

    try:
        rows = sheets.get_leads_rows()  # Single API call, ~0.40s for 730 rows

        # Build talent name → id map once (avoid N+1 per-row queries — Anti-Pattern in RESEARCH.md)
        talent_map: dict[str, int] = {
            t.name: t.id for t in db.query(Talent).all()
        }

        records_synced = 0
        for row in rows:
            # None = "Sin talento asignado" bucket (D-33)
            talent_id = talent_map.get(row.talento_mencionado) if row.talento_mencionado else None

            existing = db.query(Lead).filter(Lead.sheet_row_id == row.sheet_row_id).first()
            if existing is None:
                existing = Lead(sheet_row_id=row.sheet_row_id)
                db.add(existing)

            existing.remitente_email = row.remitente_email
            existing.remitente_nombre = row.remitente_nombre
            existing.asunto = row.asunto
            existing.fecha_recepcion = _parse_fecha(row.fecha_recepcion)
            existing.talent_id = talent_id
            existing.status_filtrado = row.status_filtrado
            existing.fuente = "Gmail"
            existing.score_calidad = row.score_calidad
            existing.bloqueado = row.bloqueado
            existing.convertido_a_prospecto = row.convertido_a_prospecto
            records_synced += 1

        db.commit()
        sync_log.status = "success"
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.records_synced = records_synced
        db.commit()
        db.refresh(sync_log)

    except Exception as exc:  # noqa: BLE001 - persist only str(exc); never store gspread objects
        db.rollback()
        sync_log.status = "error"
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.error_message = str(exc)  # str() only — never repr(response) or log objects
        db.commit()
        db.refresh(sync_log)

    return sync_log


def sync_trello(db: Session) -> SyncLog:
    """Sync Trello cards from the 6 mapped lists into the local TrelloCard table.

    Upserts by trello_card_id (natural key). Idempotent: second run with
    identical cards inserts zero new rows.

    Concurrency guard filters by source='trello' only (CR-03 / T-04-06).
    A running pipedrive or sheets SyncLog does NOT block this function.

    Security (T-04-05): on error, persist only str(exc) to SyncLog.error_message
    — never log the trello client or response objects (query params carry secrets).
    """
    # 1. Concurrency guard — filter by source='trello' only (CR-03).
    running = (
        db.query(SyncLog)
        .filter(SyncLog.source == "trello", SyncLog.status == "running")
        .order_by(SyncLog.started_at.desc())
        .first()
    )
    if running is not None and not _is_stale(running):
        return running

    # 2. Write SyncLog row immediately so concurrent callers see "running".
    sync_log = SyncLog(
        source="trello",
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db.add(sync_log)
    db.commit()
    db.refresh(sync_log)

    client = None  # CR-02: initialize before try so finally can safely close
    try:
        client = trello._client()

        # Preload all deals once for deal linkage (avoid N+1 queries).
        all_deals = db.query(Deal).all()

        records_synced = 0
        for list_id, state in trello.LIST_STATE_MAP.items():
            cards = trello.get_list_cards(client, list_id)
            for card in cards:
                card_id = card["id"]
                card_name = card.get("name", "")
                card_due = card.get("due")
                card_desc = card.get("desc", "")

                # Resolve local deal_id (desc header first, then fuzzy match).
                deal_id = trello_service.resolve_deal_id(db, card_desc, card_name)

                # Resolve the linked Deal object for the collection-date fallback chain.
                linked_deal = None
                if deal_id is not None:
                    linked_deal = db.query(Deal).filter(Deal.id == deal_id).first()

                collection_date = trello_service.resolve_collection_date(card_due, linked_deal)

                # Parse pipedrive_deal_id_desc for storage (raw from desc header).
                pipedrive_deal_id_desc = trello_service._extract_deal_id_from_desc(card_desc)

                # Upsert TrelloCard by trello_card_id.
                existing = (
                    db.query(TrelloCard)
                    .filter(TrelloCard.trello_card_id == card_id)
                    .first()
                )
                if existing is None:
                    existing = TrelloCard(trello_card_id=card_id)
                    db.add(existing)

                existing.name = card_name
                existing.list_id = list_id
                existing.list_name = _list_name_for(list_id)
                existing.list_state = state
                existing.deal_id = deal_id
                existing.pipedrive_deal_id_desc = pipedrive_deal_id_desc
                existing.collection_date = collection_date

                records_synced += 1

        db.commit()

        if TRELLO_AUTO_CREATE_ENABLED:
            # Reconciliation: auto-create Contrato-list cards for won deals with no card.
            # Idempotency guard (T-04-07 / Pitfall 1): build the set of already-linked
            # pipedrive_ids from TrelloCard rows before querying won deals.
            linked_pipedrive_ids: set[int] = {
                row[0]
                for row in db.query(TrelloCard.pipedrive_deal_id_desc)
                .filter(TrelloCard.pipedrive_deal_id_desc.isnot(None))
                .all()
            }
            linked_deal_ids: set[int] = {
                row[0]
                for row in db.query(TrelloCard.deal_id)
                .filter(TrelloCard.deal_id.isnot(None))
                .all()
            }

            won_deals = db.query(Deal).filter(Deal.status == "won").all()
            for won_deal in won_deals:
                # Skip if already linked by pipedrive_deal_id_desc or by deal_id.
                if (
                    won_deal.pipedrive_id in linked_pipedrive_ids
                    or won_deal.id in linked_deal_ids
                ):
                    continue

                desc = trello_service._make_card_desc(won_deal.pipedrive_id)
                response = trello.create_card(
                    client,
                    trello.CONTRATO_LIST_ID,
                    won_deal.title,
                    desc=desc,
                )

                collection_date = trello_service.resolve_collection_date(
                    response.get("due"), won_deal
                )

                card_id_new = response.get("id")
                if card_id_new is None:  # WR-02: malformed Trello response, skip this card
                    continue

                new_card = TrelloCard(
                    trello_card_id=card_id_new,
                    name=won_deal.title,
                    list_id=trello.CONTRATO_LIST_ID,
                    list_name="Contrato",
                    list_state="ejecucion",
                    deal_id=won_deal.id,
                    pipedrive_deal_id_desc=won_deal.pipedrive_id,
                    collection_date=collection_date,
                )
                db.add(new_card)

                # Add to guard sets so subsequent won_deals in the same run are checked.
                linked_pipedrive_ids.add(won_deal.pipedrive_id)
                linked_deal_ids.add(won_deal.id)

                records_synced += 1

            db.commit()
        sync_log.status = "success"
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.records_synced = records_synced
        db.commit()
        db.refresh(sync_log)

    except Exception as exc:  # noqa: BLE001 - persist only str(exc); never store trello objects
        db.rollback()
        sync_log.status = "error"
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.error_message = str(exc)  # str() only — never repr(client/response)
        db.commit()
        db.refresh(sync_log)
    finally:
        if client is not None:
            client.close()  # CR-02: always release httpx connection pool

    return sync_log


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_LIST_NAMES: dict[str, str] = {
    "69312ac640ae158381706ff8": "Contrato",
    "69312acb534b0e80508bf4e5": "Firmar contrato todos",
    "69312ad08fe346b82da12e1d": "Enviar factura",
    "69312ad63829ef3ac9967d1a": "Cobrar",
    "69312adeac51905b84f53c35": "Enviar encuesta",
    "69d8336e46709e935f4307fe": "Finalizados",
}


def _list_name_for(list_id: str) -> str:
    """Return the human-readable Trello list name for a given list_id."""
    return _LIST_NAMES.get(list_id, list_id)
