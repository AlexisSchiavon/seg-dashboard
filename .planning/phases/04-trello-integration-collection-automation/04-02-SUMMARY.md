---
phase: 04-trello-integration-collection-automation
plan: 02
subsystem: integrations, services, sync, testing
tags: [trello, sync, fuzzy-match, collection-date, sqlalchemy, apscheduler, pytest]

# Dependency graph
requires:
  - phase: 04-01
    provides: TrelloCard model, trello.py wrapper (LIST_STATE_MAP, get_list_cards), mock_trello_transport fixture, seed_trello_cards fixture, Wave 0 test stubs
  - phase: 02-pipedrive-crm-sync
    provides: sync_sheets analog (concurrency guard pattern, SyncLog upsert lifecycle, str(exc) error convention)
provides:
  - app/services/trello_service.py (deal linkage + collection-date helpers)
  - sync_trello in app/sync/jobs.py (read + upsert job)
  - sync_trello wired in app/sync/scheduler.py and app/routers/sync.py
  - 6 Wave 2 test stubs turned green in tests/test_trello.py
affects:
  - 04-03 (auto-create card — uses same trello._client() pattern; no new deps)
  - 04-04 (income_projection math — reads TrelloCard.list_state rows populated by sync_trello)

# Tech tracking
tech-stack:
  added: []  # Zero new packages (T-04-SC: no new installs this phase)
  patterns:
    - "Per-source concurrency guard: SyncLog.source == 'trello' filter (CR-03/T-04-06)"
    - "Collection-date fallback chain: card.due[:10] → add_time+2mo (divmod month arithmetic) → today first-of-month"
    - "Fuzzy match: SequenceMatcher ratio >= 0.70; brand_prefix fast-path substring filter"
    - "Deal linkage two-step: desc header _DEAL_ID_RE → pipedrive_id lookup; then fuzzy title fallback"
    - "Monkey-patch pattern for trello._client() in tests (no dependency injection needed)"

key-files:
  created:
    - app/services/trello_service.py
  modified:
    - app/sync/jobs.py (imports + sync_trello + _list_name_for + _LIST_NAMES)
    - app/sync/scheduler.py (import + sync_trello call in _run_all_syncs)
    - app/routers/sync.py (import + sync_trello call in _run_sync_in_background)
    - tests/test_trello.py (6 Wave 2 stubs filled in)

key-decisions:
  - "T-04-04 mitigated: _DEAL_ID_RE = re.compile(r'\\[seg:deal_id=(\\d+)\\]') — only digits captured, no eval"
  - "T-04-05 mitigated: error handler uses str(exc) only, never repr(client) or repr(response)"
  - "T-04-06 mitigated: SyncLog.source == 'trello' per-source guard; pipedrive/sheets running log does not block trello"
  - "list_name stored via hardcoded _LIST_NAMES dict in jobs.py (avoids extra API call; names are static for this board)"
  - "linked_deal re-fetched from db by id after resolve_deal_id to pass Deal object to resolve_collection_date"

patterns-established:
  - "trello_service module: pure functions taking (str|None, Deal|None) — no DB dependency except resolve_deal_id"
  - "sync_trello follows exact sync_sheets structural pattern (concurrency guard → SyncLog running → try/commit/success → except/rollback/error)"

requirements-completed: [TRELLO-01, TRELLO-02]

# Metrics
duration: 5min
completed: 2026-06-15
---

# Phase 04 Plan 02: sync_trello Sync Slice Summary

**Trello sync job with deal-linkage service (fuzzy match + desc-header parse), collection-date fallback chain (due → add_time+2mo → today), upsert by trello_card_id, per-source concurrency guard, and scheduler/manual-trigger wiring**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-15T04:08:30Z
- **Completed:** 2026-06-15T04:13:22Z
- **Tasks:** 3 of 3
- **Files modified:** 5

## Accomplishments

- Created `app/services/trello_service.py` with all required helpers: `_normalize` (NFKD+ASCII+lower+strip), `_brand_prefix` (split on ` - ` or ` x `), `_DEAL_ID_RE` regex (digits-only, T-04-04), `_extract_deal_id_from_desc`, `fuzzy_match_deal` (SequenceMatcher >= 0.70), `resolve_collection_date` (3-step fallback chain), `resolve_deal_id` (desc parse first, fuzzy fallback)
- Added `sync_trello(db)` to `app/sync/jobs.py` mirroring `sync_sheets` pattern: per-source concurrency guard on `SyncLog.source == 'trello'`, SyncLog lifecycle (running → success|error), iterates 6 LIST_STATE_MAP entries, upserts TrelloCard by `trello_card_id`, resolves deal linkage and collection date per card
- Wired `sync_trello` into `app/sync/scheduler.py` `_run_all_syncs` (Pipedrive → Sheets → Trello) and `app/routers/sync.py` `_run_sync_in_background`
- Filled in 6 Wave 2 test stubs in `tests/test_trello.py`; all pass green
- Full suite: 118 passed, 4 skipped (Wave 3+4 stubs), 0 regressions

## Task Commits

1. **Task 1: trello_service linkage and collection-date helpers** - `05fd7df` (feat)
2. **Task 2: sync_trello read and upsert job** - `9fa2d3f` (feat)
3. **Task 3: Wire sync_trello into scheduler and manual trigger** - `207e6e1` (feat)

## Files Created/Modified

- `app/services/trello_service.py` - Deal linkage helpers and collection-date fallback chain
- `app/sync/jobs.py` - sync_trello function + _list_name_for helper + _LIST_NAMES dict; updated imports
- `app/sync/scheduler.py` - import sync_trello; add sync_trello(db) call in _run_all_syncs
- `app/routers/sync.py` - import sync_trello; add sync_trello(db) call in _run_sync_in_background
- `tests/test_trello.py` - 6 Wave 2 stubs implemented (collection_date_from_due, collection_date_fallback, sync_trello_upserts_cards, ignores_otros_pendientes, concurrency_guard, source_filter_isolated)

## Decisions Made

- `_DEAL_ID_RE = re.compile(r'\[seg:deal_id=(\d+)\]')` captures only digit sequences (T-04-04 mitigated). Non-numeric desc text yields `None` and never reaches an integer lookup.
- Error handler in `sync_trello` persists only `str(exc)` — never `repr(client)` or `repr(response)` (T-04-05 mitigated). Trello auth query params would appear in `repr(request.url)`.
- Per-source guard: `SyncLog.source == "trello"` filter ensures a running pipedrive or sheets log does NOT block `sync_trello` (T-04-06 / CR-03 mitigated).
- `list_name` stored via hardcoded `_LIST_NAMES` dict in `jobs.py` — avoids a second API call per list; Trello list names for this board are static per RESEARCH.md.
- `linked_deal` re-fetched by `deal_id` from DB after `resolve_deal_id` returns so that the `Deal` object is available for `resolve_collection_date`'s `add_time` fallback.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

The following test stubs remain intentionally skipped (Wave 3+4 strategy):

| Test | File | Wave |
|------|------|------|
| test_auto_create_card_for_won_deal | tests/test_trello.py | Wave 3 (Plan 04-03) |
| test_no_duplicate_card_creation | tests/test_trello.py | Wave 3 (Plan 04-03) |
| test_card_desc_contains_deal_id | tests/test_trello.py | Wave 3 (Plan 04-03) |
| test_income_projection_math | tests/test_trello.py | Wave 4 (Plan 04-04) |

## Threat Surface Scan

No new network endpoints introduced. All threat mitigations from the plan's threat model were applied:

| Threat | Status |
|--------|--------|
| T-04-04: Tampering via desc deal-id parse | Mitigated: `_DEAL_ID_RE` accepts digits only |
| T-04-05: Info disclosure via error path | Mitigated: `str(exc)` only in `sync_trello` error handler |
| T-04-06: DoS via cross-source sync blocking | Mitigated: `SyncLog.source == "trello"` per-source guard |

## Self-Check

---
*Phase: 04-trello-integration-collection-automation*
*Completed: 2026-06-15*
