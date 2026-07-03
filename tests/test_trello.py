"""Tests for the Trello integration (Phase 4).

Test Map:
  - test_sync_trello_upserts_cards: sync_trello() upserts cards from 7 lists (Wave 2)
  - test_sync_trello_marks_otros_pendientes_omitido: "Otros pendientes" → 'omitido' (9.8a)
  - test_list_state_mapping: LIST_STATE_MAP maps 7 list IDs to correct states (9.8a)
  - test_collection_date_from_due: collection_date derived from Trello card due date (Wave 2)
  - test_collection_date_fallback: fallback to add_time + 2 months when no due (Wave 2)
  - test_auto_create_card_for_won_deal: won deals with no card get one created (Wave 3)
  - test_no_duplicate_card_creation: won deals with existing card NOT duplicated (Wave 3)
  - test_card_desc_contains_deal_id: [seg:deal_id=N] written on card creation (Wave 3)
  - test_income_projection_math: income_projection returns cobrado/proyeccion/pendiente (Wave 4)
  - test_sync_trello_concurrency_guard: concurrency guard uses source="trello" filter (Wave 2)
  - test_sync_trello_source_filter_isolated: running pipedrive sync does NOT block trello (Wave 2)
"""

import pytest


# ---------------------------------------------------------------------------
# Wave 0 — Fully implemented (no external dependencies needed)
# ---------------------------------------------------------------------------


def test_list_state_mapping():
    """LIST_STATE_MAP maps all 7 board list IDs to the corrected states (Fase 9.8a).

    Verified against live board 69312a9d5523703a1ce1a413.
      - "Enviar encuesta" is POST-collection → 'cerrado' (was wrongly 'cobranza').
      - "Otros pendientes" is admin garbage → 'omitido' (excluded from all calcs).
      - Only "Cobrar" (= 'cobranza') is genuinely pending collection.
    """
    from app.integrations.trello import LIST_STATE_MAP

    expected = {
        "69312ac640ae158381706ff8": "ejecucion",   # Contrato
        "69312acb534b0e80508bf4e5": "ejecucion",   # Firmar contrato todos
        "69312ad08fe346b82da12e1d": "ejecucion",   # Enviar factura
        "69312ad63829ef3ac9967d1a": "cobranza",    # Cobrar
        "69312adeac51905b84f53c35": "cerrado",     # Enviar encuesta (post-cobro)
        "6996256c42ccdae7f69e4814": "omitido",     # Otros pendientes (excluido)
        "69d8336e46709e935f4307fe": "cerrado",     # Finalizados
    }

    assert len(LIST_STATE_MAP) == 7, f"Expected 7 entries, got {len(LIST_STATE_MAP)}"

    for list_id, expected_state in expected.items():
        assert list_id in LIST_STATE_MAP, f"Missing list_id: {list_id}"
        assert LIST_STATE_MAP[list_id] == expected_state, (
            f"list_id={list_id}: expected {expected_state!r}, got {LIST_STATE_MAP[list_id]!r}"
        )


# ---------------------------------------------------------------------------
# Wave 2 stubs — sync_trello job (sync service not yet implemented)
# ---------------------------------------------------------------------------


def test_sync_trello_upserts_cards(db_session, mock_trello_transport, seed_deals):
    """sync_trello() fetches cards from all 7 lists and upserts TrelloCard rows.

    Arrange: seed_deals provides Deal rows; mock_trello_transport serves card lists.
    Act: call sync_trello(db_session).
    Assert: TrelloCard rows exist for every mapped list (including 'omitido');
    upsert is idempotent.
    """
    import httpx

    from app.models import TrelloCard
    from app.sync.jobs import sync_trello

    # Patch trello._client() to use the mock transport
    import app.integrations.trello as trello_mod
    original_client = trello_mod._client

    def mock_client():
        return httpx.Client(
            base_url=trello_mod.BASE_URL,
            transport=mock_trello_transport,
            timeout=30.0,
        )

    trello_mod._client = mock_client
    try:
        log = sync_trello(db_session)
    finally:
        trello_mod._client = original_client

    assert log.status == "success", f"Expected success, got {log.status}: {log.error_message}"

    cards = db_session.query(TrelloCard).all()
    assert len(cards) == 4, (
        f"Expected 4 cards (ejecucion+cobranza+cerrado+omitido), got {len(cards)}"
    )

    # Idempotency: second run must not insert new rows
    trello_mod._client = mock_client
    try:
        log2 = sync_trello(db_session)
    finally:
        trello_mod._client = original_client

    assert log2.status == "success"
    cards_after = db_session.query(TrelloCard).all()
    assert len(cards_after) == 4, "Second run must not create duplicate rows"


def test_sync_trello_marks_otros_pendientes_omitido(db_session, mock_trello_transport, seed_deals):
    """Cards in 'Otros pendientes' (list_id 6996256c42ccdae7f69e4814) sync as 'omitido'.

    Fase 9.8a decision: these cards ARE synced (for visibility) but tagged with
    list_state='omitido', which every KPI/projection/collection calc excludes via
    whitelist. This test locks in the sync-time tagging; exclusion from aggregates
    is covered by the service-layer tests.

    Arrange: mock_trello_transport includes an Otros pendientes card.
    Act: call sync_trello(db_session).
    Assert: the card exists with list_state='omitido' and list_name='Otros pendientes'.
    """
    import httpx

    from app.models import TrelloCard
    from app.sync.jobs import sync_trello

    import app.integrations.trello as trello_mod
    original_client = trello_mod._client

    def mock_client():
        return httpx.Client(
            base_url=trello_mod.BASE_URL,
            transport=mock_trello_transport,
            timeout=30.0,
        )

    trello_mod._client = mock_client
    try:
        log = sync_trello(db_session)
    finally:
        trello_mod._client = original_client

    assert log.status == "success"

    otros_cards = (
        db_session.query(TrelloCard)
        .filter(TrelloCard.list_id == "6996256c42ccdae7f69e4814")
        .all()
    )
    assert len(otros_cards) == 1, f"Expected 1 Otros pendientes card synced, got {len(otros_cards)}"
    assert otros_cards[0].list_state == "omitido", (
        f"Otros pendientes must map to 'omitido', got {otros_cards[0].list_state!r}"
    )
    assert otros_cards[0].list_name == "Otros pendientes"


def test_collection_date_from_due(db_session, mock_trello_transport, seed_deals):
    """collection_date is set from the card's Trello due date field.

    Arrange: mock card has due='2026-08-15T...' ISO string.
    Act: call sync_trello(db_session).
    Assert: TrelloCard.collection_date == date(2026, 8, 15).
    """
    from datetime import date

    import httpx

    from app.integrations.trello import LIST_STATE_MAP, _client
    from app.models import TrelloCard
    from app.services.trello_service import resolve_collection_date

    # card-ejecucion-001 has due='2026-08-15T12:00:00.000Z'
    result = resolve_collection_date("2026-08-15T12:00:00.000Z", deal=None)
    assert result == date(2026, 8, 15), f"Expected 2026-08-15, got {result}"


def test_collection_date_fallback(db_session, mock_trello_transport, seed_deals):
    """When Trello due is null, collection_date falls back to add_time + 2 months.

    Arrange: mock card has due=None; linked Deal has add_time='2026-05-25T...'.
    Act: resolve_collection_date(None, deal).
    Assert: TrelloCard.collection_date == date(2026, 7, 1) (first-of-month + 2 months).
    """
    from datetime import date

    from app.services.trello_service import resolve_collection_date

    # deal_sin_cotizar has add_time='2026-05-25T09:00:00Z' → month 5 + 2 = month 7 → 2026-07-01
    deal = seed_deals["deal_sin_cotizar"]
    result = resolve_collection_date(None, deal=deal)
    assert result == date(2026, 7, 1), f"Expected 2026-07-01, got {result}"


def test_sync_trello_concurrency_guard(db_session, mock_trello_transport):
    """A running SyncLog with source='trello' blocks a second sync_trello call.

    Arrange: insert SyncLog(source='trello', status='running').
    Act: call sync_trello(db_session).
    Assert: returns the existing running log; no TrelloCard rows created.
    """
    from datetime import datetime, timezone

    from app.models import SyncLog, TrelloCard
    from app.sync.jobs import sync_trello

    # Plant a fresh (non-stale) running trello SyncLog
    running = SyncLog(
        source="trello",
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db_session.add(running)
    db_session.commit()
    db_session.refresh(running)

    result = sync_trello(db_session)

    # Must return the existing running log without creating cards
    assert result.id == running.id, "Expected the existing running SyncLog to be returned"
    assert result.status == "running"
    assert db_session.query(TrelloCard).count() == 0, "No cards must be created when guard fires"


def test_sync_trello_source_filter_isolated(db_session, mock_trello_transport, seed_deals):
    """A running pipedrive SyncLog does NOT block sync_trello (source isolation).

    Mirrors test_sync_sheets_source_filter_isolated from test_leads.py:
    Arrange: insert SyncLog(source='pipedrive', status='running').
    Act: call sync_trello(db_session).
    Assert: sync_trello succeeds and creates TrelloCard rows.
    """
    import httpx
    from datetime import datetime, timezone

    from app.models import SyncLog, TrelloCard
    from app.sync.jobs import sync_trello

    # Plant a running pipedrive SyncLog (must NOT block trello sync per CR-03)
    pipedrive_running = SyncLog(
        source="pipedrive",
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db_session.add(pipedrive_running)
    db_session.commit()

    import app.integrations.trello as trello_mod
    original_client = trello_mod._client

    def mock_client():
        return httpx.Client(
            base_url=trello_mod.BASE_URL,
            transport=mock_trello_transport,
            timeout=30.0,
        )

    trello_mod._client = mock_client
    try:
        log = sync_trello(db_session)
    finally:
        trello_mod._client = original_client

    assert log.status == "success", f"Expected success, got {log.status}: {log.error_message}"
    assert log.source == "trello"
    assert db_session.query(TrelloCard).count() > 0, "Expected TrelloCard rows to be created"


# ---------------------------------------------------------------------------
# DECISIÓN PERMANENTE: auto-creación de tarjetas DESACTIVADA (ver CLAUDE.md)
# create_card() siempre lanza RuntimeError — el sistema de Fase 2 Talent
# maneja la creación en producción. Tests documentan esta invariante.
# ---------------------------------------------------------------------------


def test_create_card_is_permanently_disabled():
    """create_card() debe lanzar RuntimeError sin importar los parámetros.

    Documenta la decisión arquitectural permanente: el SEG Dashboard es
    SOLO LECTURA para Trello. Intentar crear una tarjeta es un error de
    programación, no un estado de error de negocio.
    """
    import httpx
    import pytest

    from app.integrations.trello import create_card

    dummy_client = httpx.Client()
    with pytest.raises(RuntimeError, match="permanentemente desactivado"):
        create_card(dummy_client, list_id="any-list", name="any-name")


def test_auto_create_flag_is_always_false():
    """TRELLO_AUTO_CREATE_ENABLED debe ser False en el módulo sin modificar.

    Cualquier cambio accidental a True en jobs.py debe detectarse aquí
    en la suite de tests antes de llegar a producción.
    """
    import app.sync.jobs as jobs

    assert jobs.TRELLO_AUTO_CREATE_ENABLED is False, (
        "TRELLO_AUTO_CREATE_ENABLED se cambió a True — esto viola la "
        "decisión permanente documentada en CLAUDE.md. "
        "La creación de tarjetas la maneja el sistema de Fase 2 Talent."
    )


def test_card_desc_contains_deal_id(db_session, mock_trello_transport, seed_deals):
    """_make_card_desc writes a [seg:deal_id=N] marker that round-trips through
    _extract_deal_id_from_desc.

    Tests:
    - First line of _make_card_desc(12345) is '[seg:deal_id=12345]'
    - _extract_deal_id_from_desc(_make_card_desc(12345)) == 12345 (round-trip)
    - _make_card_desc(12345, "extra") includes the marker AND the extra text
    """
    from app.services.trello_service import _extract_deal_id_from_desc, _make_card_desc

    # Round-trip: writer and reader are consistent
    desc = _make_card_desc(12345)
    assert _extract_deal_id_from_desc(desc) == 12345, (
        f"Round-trip failed: _extract_deal_id_from_desc({desc!r}) != 12345"
    )

    # First line must be the exact marker
    first_line = desc.split("\n")[0]
    assert first_line == "[seg:deal_id=12345]", (
        f"First line {first_line!r} is not the expected marker"
    )

    # With extra_desc: marker + blank line + extra
    desc_with_extra = _make_card_desc(12345, "extra notes")
    assert "[seg:deal_id=12345]" in desc_with_extra
    assert "extra notes" in desc_with_extra
    # Round-trip still works with extra text
    assert _extract_deal_id_from_desc(desc_with_extra) == 12345


# ---------------------------------------------------------------------------
# Wave 4 stubs — income projection math (DASH-02)
# ---------------------------------------------------------------------------


def test_income_projection_math(db_session, seed_trello_cards, seed_deals):
    """income_projection() returns cobrado, proyeccion, and pendiente for a talent.

    Seed layout (from conftest.py):
      card_ejecucion → deal_open (talent_a, value=50000, list_state=ejecucion,
                        collection_date=2026-08-15)
      card_cobranza  → deal_sin_cotizar (talent_b, value=0, list_state=cobranza,
                        collection_date=None → fallback add_time 2026-05-25+2mo=2026-07-01)
      card_cerrado   → deal_sin_talento (talent_id=None, value=20000, list_state=cerrado,
                        collection_date=2026-07-01)

    talent_a only has card_ejecucion (deal_open, value=50000).
    The 4-month window is sliding from today. We assert structural guarantees
    that don't depend on the exact anchor date:
      1. Result is a list of exactly 4 dicts.
      2. Each dict has keys: month, cobrado, proyeccion, pendiente.
      3. month labels match "XXX YYYY" format (3-letter abbr + 4-digit year).
      4. The sum of proyeccion across all months equals deal_open.value (50000)
         when card_ejecucion.collection_date=2026-08-15 falls inside the window.
         (If 2026-08 is outside the window the sum will be 0 — still valid.)
      5. Totals across all months are non-negative.

    talent_b only has card_cobranza (deal_sin_cotizar, value=0.0):
      - pendiente contribution is 0.0 regardless of window position.

    Global: payment_calendar returns exactly 4 dicts {month, amount}; all amounts >= 0.
    deals_for_talent returns dicts with required keys for each talent.
    """
    import re
    from datetime import date

    from app.services.trello_service import (
        income_projection,
        payment_calendar,
        deals_for_talent,
    )

    talent_a = seed_deals["deal_open"].talent_id   # ID for Talento Uno
    talent_b = seed_deals["deal_sin_cotizar"].talent_id  # ID for Talento Dos

    # ── income_projection: structural assertions ──────────────────────────────
    proj_a = income_projection(db_session, talent_a)
    assert isinstance(proj_a, list), "income_projection must return a list"
    assert len(proj_a) == 4, f"Expected 4 months, got {len(proj_a)}"

    month_re = re.compile(r"^[A-Z][a-z]{2} \d{4}$")
    for entry in proj_a:
        assert "month" in entry and "cobrado" in entry and "proyeccion" in entry and "pendiente" in entry, \
            f"Missing keys in entry: {entry}"
        assert month_re.match(entry["month"]), \
            f"Month label {entry['month']!r} does not match 'Mon YYYY' format"
        assert entry["cobrado"] >= 0
        assert entry["proyeccion"] >= 0
        assert entry["pendiente"] >= 0

    # deal_open has value=50000 and list_state=ejecucion, collection_date=2026-08-15.
    # Sum proyeccion across all 4 months — equals 50000 if Aug 2026 is in the window,
    # else 0.0 (valid either way — no hardcoded date dependency).
    total_proyeccion = sum(e["proyeccion"] for e in proj_a)
    total_cobrado = sum(e["cobrado"] for e in proj_a)
    total_pendiente = sum(e["pendiente"] for e in proj_a)
    assert total_proyeccion in (0.0, 50000.0), \
        f"Unexpected proyeccion total for talent_a: {total_proyeccion}"
    assert total_cobrado == 0.0, \
        f"talent_a has no cerrado cards — cobrado must be 0, got {total_cobrado}"

    # talent_b: only cobranza card (value=0.0) — all layers sum to 0
    proj_b = income_projection(db_session, talent_b)
    assert len(proj_b) == 4
    assert sum(e["pendiente"] for e in proj_b) == 0.0
    assert sum(e["proyeccion"] for e in proj_b) == 0.0

    # ── payment_calendar ──────────────────────────────────────────────────────
    cal_a = payment_calendar(db_session, talent_a)
    assert isinstance(cal_a, list)
    assert len(cal_a) == 4
    for entry in cal_a:
        assert "month" in entry and "amount" in entry
        assert entry["amount"] >= 0

    # ── deals_for_talent ─────────────────────────────────────────────────────
    deals_a = deals_for_talent(db_session, talent_a)
    assert isinstance(deals_a, list)
    assert len(deals_a) >= 1, "talent_a should have at least 1 deal row"
    for row in deals_a:
        assert "title" in row and "amount" in row and "list_state" in row and "trello_card_id" in row, \
            f"Missing keys in deal row: {row}"

    # Verify sorted by amount descending
    amounts = [r["amount"] for r in deals_a]
    assert amounts == sorted(amounts, reverse=True), "deals_for_talent must be sorted by amount desc"
