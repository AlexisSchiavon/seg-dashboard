"""Tests for the Trello integration (Phase 4).

Test Map:
  - test_sync_trello_upserts_cards: sync_trello() upserts cards from 6 lists (Wave 2)
  - test_sync_trello_ignores_otros_pendientes: cards in "Otros pendientes" NOT synced (Wave 2)
  - test_list_state_mapping: LIST_STATE_MAP maps 6 list IDs to correct states (Wave 0 — GREEN)
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
    """LIST_STATE_MAP maps all 6 active list IDs to the correct states.

    Verified against live board 69312a9d5523703a1ce1a413 on 2026-06-14.
    "Otros pendientes" (6996256c42ccdae7f69e4814) must NOT appear in the map.
    """
    from app.integrations.trello import LIST_STATE_MAP

    expected = {
        "69312ac640ae158381706ff8": "ejecucion",   # Contrato
        "69312acb534b0e80508bf4e5": "ejecucion",   # Firmar contrato todos
        "69312ad08fe346b82da12e1d": "ejecucion",   # Enviar factura
        "69312ad63829ef3ac9967d1a": "cobranza",    # Cobrar
        "69312adeac51905b84f53c35": "cobranza",    # Enviar encuesta
        "69d8336e46709e935f4307fe": "cerrado",     # Finalizados
    }

    assert len(LIST_STATE_MAP) == 6, f"Expected 6 entries, got {len(LIST_STATE_MAP)}"

    for list_id, expected_state in expected.items():
        assert list_id in LIST_STATE_MAP, f"Missing list_id: {list_id}"
        assert LIST_STATE_MAP[list_id] == expected_state, (
            f"list_id={list_id}: expected {expected_state!r}, got {LIST_STATE_MAP[list_id]!r}"
        )

    # Otros pendientes must be absent
    assert "6996256c42ccdae7f69e4814" not in LIST_STATE_MAP, (
        "Otros pendientes list ID must NOT be in LIST_STATE_MAP"
    )


# ---------------------------------------------------------------------------
# Wave 2 stubs — sync_trello job (sync service not yet implemented)
# ---------------------------------------------------------------------------


def test_sync_trello_upserts_cards(db_session, mock_trello_transport, seed_deals):
    """sync_trello() fetches cards from all 6 lists and upserts TrelloCard rows.

    Arrange: seed_deals provides Deal rows; mock_trello_transport serves card lists.
    Act: call sync_trello(db_session).
    Assert: TrelloCard rows exist for all non-ignored lists; upsert is idempotent.
    """
    pytest.skip("Wave 2: implemented when sync_trello / trello_service lands")


def test_sync_trello_ignores_otros_pendientes(db_session, mock_trello_transport, seed_deals):
    """Cards in 'Otros pendientes' (list_id 6996256c42ccdae7f69e4814) are not synced.

    Arrange: mock_trello_transport includes Otros pendientes cards.
    Act: call sync_trello(db_session).
    Assert: no TrelloCard row has list_id == '6996256c42ccdae7f69e4814'.
    """
    pytest.skip("Wave 2: implemented when sync_trello / trello_service lands")


def test_collection_date_from_due(db_session, mock_trello_transport, seed_deals):
    """collection_date is set from the card's Trello due date field.

    Arrange: mock card has due='2026-08-15T...' ISO string.
    Act: call sync_trello(db_session).
    Assert: TrelloCard.collection_date == date(2026, 8, 15).
    """
    pytest.skip("Wave 2: implemented when sync_trello / trello_service lands")


def test_collection_date_fallback(db_session, mock_trello_transport, seed_deals):
    """When Trello due is null, collection_date falls back to add_time + 2 months.

    Arrange: mock card has due=None; linked Deal has add_time='2026-05-20T...'.
    Act: call sync_trello(db_session).
    Assert: TrelloCard.collection_date == date(2026, 7, 20) (2-month offset).
    """
    pytest.skip("Wave 2: implemented when sync_trello / trello_service lands")


def test_sync_trello_concurrency_guard(db_session, mock_trello_transport):
    """A running SyncLog with source='trello' blocks a second sync_trello call.

    Arrange: insert SyncLog(source='trello', status='running').
    Act: call sync_trello(db_session).
    Assert: returns the existing running log; no TrelloCard rows created.
    """
    pytest.skip("Wave 2: implemented when sync_trello / trello_service lands")


def test_sync_trello_source_filter_isolated(db_session, mock_trello_transport, seed_deals):
    """A running pipedrive SyncLog does NOT block sync_trello (source isolation).

    Mirrors test_sync_sheets_source_filter_isolated from test_leads.py:
    Arrange: insert SyncLog(source='pipedrive', status='running').
    Act: call sync_trello(db_session).
    Assert: sync_trello succeeds and creates TrelloCard rows.
    """
    pytest.skip("Wave 2: implemented when sync_trello / trello_service lands")


# ---------------------------------------------------------------------------
# Wave 3 stubs — auto-create card for won deals (TRELLO-03)
# ---------------------------------------------------------------------------


def test_auto_create_card_for_won_deal(db_session, mock_trello_transport, seed_deals):
    """Won deals with no existing TrelloCard get a card created in CONTRATO_LIST_ID.

    Arrange: deal_open in seed_deals; no TrelloCard with matching deal_id.
    Act: call auto_create_cards_for_won_deals(db_session) or sync_trello post-win.
    Assert: create_card was called with idList=CONTRATO_LIST_ID; TrelloCard row created.
    """
    pytest.skip("Wave 3: implemented when auto_create_cards / won-deal watcher lands")


def test_no_duplicate_card_creation(db_session, mock_trello_transport, seed_trello_cards):
    """Won deals that already have a TrelloCard do NOT get a second card created.

    Arrange: seed_trello_cards provides a TrelloCard linked to a won deal.
    Act: call auto_create_cards_for_won_deals(db_session).
    Assert: create_card is NOT called for deals that already have a card.
    """
    pytest.skip("Wave 3: implemented when auto_create_cards / won-deal watcher lands")


def test_card_desc_contains_deal_id(db_session, mock_trello_transport, seed_deals):
    """When creating a card for a won deal, desc includes '[seg:deal_id=N]' header.

    Arrange: a won deal with pipedrive_id=1001 and no TrelloCard.
    Act: call auto_create_cards_for_won_deals(db_session).
    Assert: the POST /cards request params include desc containing '[seg:deal_id=1001]'.
    """
    pytest.skip("Wave 3: implemented when auto_create_cards / won-deal watcher lands")


# ---------------------------------------------------------------------------
# Wave 4 stubs — income projection math (DASH-02)
# ---------------------------------------------------------------------------


def test_income_projection_math(db_session, seed_trello_cards, seed_deals):
    """income_projection() returns cobrado, proyeccion, and pendiente for a talent.

    Arrange: TrelloCard rows linked to deals across cerrado/cobranza/ejecucion states.
    Act: call income_projection(db_session, talent_id=X).
    Assert: result is a dict with keys cobrado (cerrado sum), proyeccion (cobranza sum),
            pendiente (ejecucion sum); math is correct against seeded commission_amount values.
    """
    pytest.skip("Wave 4: implemented when income_projection service function lands")
