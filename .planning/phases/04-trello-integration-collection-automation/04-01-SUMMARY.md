---
phase: 04-trello-integration-collection-automation
plan: 01
subsystem: database, integrations, testing
tags: [trello, httpx, sqlalchemy, alembic, pytest, sqlite]

# Dependency graph
requires:
  - phase: 03-google-sheets-leads-integration
    provides: Lead model and migration pattern (Lead class, sheet_row_id unique index, seed_leads fixture) used as style analog for TrelloCard
  - phase: 02-pipedrive-crm-sync
    provides: pipedrive.py httpx wrapper pattern (_client, _auth_params, get_with_retry usage) used as structural analog for trello.py
provides:
  - TrelloCard SQLAlchemy model (trello_cards table) with FK to deals.id
  - Alembic migration ee55974a0232 chaining from d48d69b17ea6 (leads)
  - app/integrations/trello.py with LIST_STATE_MAP (6 entries), CONTRATO_LIST_ID, get_list_cards, create_card
  - tests/test_trello.py with 11 Wave 0 stubs (test_list_state_mapping green, 10 others skip)
  - tests/conftest.py fixtures: mock_trello_transport and seed_trello_cards
affects:
  - 04-02 (sync_trello job — builds against TrelloCard model and get_list_cards)
  - 04-03 (auto-create card for won deals — builds against create_card and CONTRATO_LIST_ID)
  - 04-04 (income_projection math and Por talento UI — builds against TrelloCard.list_state and seed_trello_cards)

# Tech tracking
tech-stack:
  added: []  # Zero new packages (Phase 4 installs nothing new — RESEARCH.md T-04-SC)
  patterns:
    - "Trello auth via query params (key + token) — not an HTTP header like Pipedrive"
    - "LIST_STATE_MAP: hardcoded dict from verified live board; absent key = ignored list"
    - "TrelloCard.deal_id FK targets deals.id (local PK), NOT deals.pipedrive_id"
    - "Test stubs: pytest.skip with Wave-N reason string; one fully-green test per wave"

key-files:
  created:
    - app/integrations/trello.py
    - alembic/versions/ee55974a0232_add_trello_cards_table.py
    - tests/test_trello.py
  modified:
    - app/models.py (TrelloCard class + date/Date imports added after Lead class)
    - tests/conftest.py (mock_trello_transport and seed_trello_cards fixtures appended)

key-decisions:
  - "Trello auth uses query params (key/token), not headers — trello.py _auth_params() dict merged into every request"
  - "LIST_STATE_MAP excludes Otros pendientes (6996256c42ccdae7f69e4814) by omission — absence = ignored"
  - "TrelloCard.deal_id FK targets deals.id (local autoincrement PK) not deals.pipedrive_id — consistent with Lead.talent_id pattern"
  - "No customFields code path in trello.py — free plan has Custom Fields Power-Up disabled (confirmed live API)"
  - "Wave 0 test strategy: implement list_state_mapping test fully now, stub all others with pytest.skip + Wave-N message"

patterns-established:
  - "Trello integration pattern: _client (no auth header) + _auth_params (query dict) + get_with_retry from base.py"
  - "Migration chaining: down_revision = 'd48d69b17ea6' ensures alembic upgrade head is deterministic"
  - "conftest fixture pattern for external APIs: MockTransport + handler matching path segments, ignoring auth params"

requirements-completed: [TRELLO-01]

# Metrics
duration: 7min
completed: 2026-06-15
---

# Phase 04 Plan 01: Trello Foundation Slice Summary

**TrelloCard SQLAlchemy model with Alembic migration (ee55974a0232), httpx trello.py wrapper with hardcoded LIST_STATE_MAP (6 list IDs), and 11 Wave 0 test stubs with test_list_state_mapping green**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-15T03:58:29Z
- **Completed:** 2026-06-15T04:05:31Z
- **Tasks:** 3 of 3
- **Files modified:** 5

## Accomplishments

- Added TrelloCard model to app/models.py with all required columns: trello_card_id (unique indexed), list_state, deal_id (FK deals.id nullable indexed), collection_date (Date), synced_at
- Created Alembic migration ee55974a0232 chaining from d48d69b17ea6 (leads) with correct Date column, ForeignKeyConstraint, and both indexes; applied to seg.db
- Created app/integrations/trello.py: BASE_URL, CONTRATO_LIST_ID, LIST_STATE_MAP (6 entries, Otros pendientes absent), _client (no auth header), _auth_params (key+token), get_list_cards (get_with_retry), create_card (POST /cards, raise_for_status); no custom-field code path
- Created tests/test_trello.py with 11 test functions: test_list_state_mapping fully green, 10 stubs with Wave-N skip reasons; all 112 tests pass, no regressions to prior 111

## Task Commits

Each task was committed atomically:

1. **Task 1: Add TrelloCard model and Alembic migration** - `86057f4` (feat)
2. **Task 2: Create trello.py httpx wrapper with LIST_STATE_MAP** - `a63f128` (feat)
3. **Task 3: Wave 0 test stubs and conftest fixtures** - `c9507de` (feat)

## Files Created/Modified

- `app/models.py` - TrelloCard(Base) class added after Lead; date + Date imports added
- `alembic/versions/ee55974a0232_add_trello_cards_table.py` - Migration creating trello_cards table with indexes and FK
- `app/integrations/trello.py` - Trello httpx wrapper: LIST_STATE_MAP, CONTRATO_LIST_ID, get_list_cards, create_card
- `tests/test_trello.py` - 11 Wave 0 test stubs; test_list_state_mapping green
- `tests/conftest.py` - mock_trello_transport and seed_trello_cards fixtures appended

## Decisions Made

- Trello auth uses query params (`key` + `token`), not HTTP headers — `_auth_params()` returns a dict merged into every `get_with_retry` params argument. This differs from Pipedrive's `x-api-token` header pattern.
- `LIST_STATE_MAP` excludes `6996256c42ccdae7f69e4814` (Otros pendientes) by omission. The sync job (Wave 2) filters using the map — absent key = ignored list.
- `TrelloCard.deal_id` FK targets `deals.id` (local autoincrement PK), NOT `deals.pipedrive_id`. Consistent with the `Lead.talent_id → talents.id` pattern throughout the codebase.
- Zero new packages installed. trello.py reuses existing httpx + get_with_retry from base.py. T-04-SC accepted.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- **Worktree merge required:** The worktree branch was created from an early commit and did not contain the project files (app/, tests/, alembic/). Merged `main` into the worktree branch before executing tasks. This is expected behavior for newly-spawned worktrees.
- **alembic upgrade head needed before revision:** The seg.db in the worktree was at the initial state. Ran `alembic upgrade head` (applying 3 prior migrations) before generating the new revision. Normal workflow.

## Known Stubs

The following test stubs exist intentionally (Wave 0 strategy):

| Test | File | Reason |
|------|------|--------|
| test_sync_trello_upserts_cards | tests/test_trello.py | Wave 2: sync_trello service not yet implemented |
| test_sync_trello_ignores_otros_pendientes | tests/test_trello.py | Wave 2: sync_trello service not yet implemented |
| test_collection_date_from_due | tests/test_trello.py | Wave 2: sync_trello service not yet implemented |
| test_collection_date_fallback | tests/test_trello.py | Wave 2: sync_trello service not yet implemented |
| test_sync_trello_concurrency_guard | tests/test_trello.py | Wave 2: sync_trello service not yet implemented |
| test_sync_trello_source_filter_isolated | tests/test_trello.py | Wave 2: sync_trello service not yet implemented |
| test_auto_create_card_for_won_deal | tests/test_trello.py | Wave 3: auto_create_cards service not yet implemented |
| test_no_duplicate_card_creation | tests/test_trello.py | Wave 3: auto_create_cards service not yet implemented |
| test_card_desc_contains_deal_id | tests/test_trello.py | Wave 3: auto_create_cards service not yet implemented |
| test_income_projection_math | tests/test_trello.py | Wave 4: income_projection service not yet implemented |

These stubs are intentional per the Wave 0 strategy (04-VALIDATION.md). Plans 04-02 through 04-04 will turn them green.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced beyond what the plan's threat model covers.

| Threat | Mitigation Status |
|--------|-------------------|
| T-04-01: key/token in query params — no logging of repr(response.request) | Mitigated: module docstring explicitly forbids it |
| T-04-02: trello_card_id unique index prevents duplicate rows | Mitigated: unique index on ix_trello_cards_trello_card_id |
| T-04-03: BASE_URL is static constant — no user-supplied URL | Accepted per threat model |
| T-04-SC: Zero new packages installed | Accepted per threat model |

## Next Phase Readiness

- Plan 04-02 (sync_trello job) can now build against TrelloCard model and get_list_cards wrapper
- Plan 04-03 (auto-create card) can build against create_card and CONTRATO_LIST_ID
- Plan 04-04 (income projection) can build against TrelloCard.list_state and seed_trello_cards fixture
- All 10 skipped stubs have exact function names matching VALIDATION.md — Plans 04-02/03/04 turn them green without renaming

---
*Phase: 04-trello-integration-collection-automation*
*Completed: 2026-06-15*
