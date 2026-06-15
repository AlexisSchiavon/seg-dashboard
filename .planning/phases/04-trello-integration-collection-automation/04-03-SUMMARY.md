---
phase: 04-trello-integration-collection-automation
plan: 03
subsystem: services, sync, testing
tags: [trello, auto-create, reconciliation, idempotency, tdd, won-deals]

# Dependency graph
requires:
  - phase: 04-02
    provides: sync_trello upsert loop, _extract_deal_id_from_desc, trello.create_card, TrelloCard model, mock_trello_transport fixture
  - phase: 04-01
    provides: TrelloCard model, CONTRATO_LIST_ID, LIST_STATE_MAP

provides:
  - app/services/trello_service.py (_make_card_desc deal-id header writer)
  - app/sync/jobs.py (reconciliation block in sync_trello -- auto-create card for won deals)
  - tests/test_trello.py (3 Wave 3 stubs turned green)

affects:
  - 04-04 (income_projection math -- TrelloCard rows now also created for won deals via auto-create)

# Tech tracking
tech-stack:
  added: []  # Zero new packages (T-04-SC: no new installs)
  patterns:
    - "TDD: RED commit (test) -> GREEN commit (feat) per task"
    - "Reconciliation idempotency: pre-scan linked_pipedrive_ids + linked_deal_ids sets before POST loop"
    - "Inline guard-set update: add to sets after create_card so same-run multi-won-deal scenario is safe"
    - "_make_card_desc format: [seg:deal_id=N] matches _DEAL_ID_RE -> round-trip fidelity guaranteed"

key-files:
  created: []
  modified:
    - app/services/trello_service.py (_make_card_desc function added after resolve_collection_date)
    - app/sync/jobs.py (reconciliation block added inside sync_trello try block after db.commit of card upserts)
    - tests/test_trello.py (3 Wave 3 stubs implemented and pytest.skip removed)

key-decisions:
  - "T-04-07 mitigated: idempotency guard uses two sets (pipedrive_deal_id_desc + deal_id) -- either match blocks creation"
  - "T-04-08 mitigated: _make_card_desc uses f-string with integer pipedrive_deal_id only -- no untrusted string in header"
  - "T-04-09 mitigated: reconciliation block inside existing try -- on error str(exc) only persisted, never client/response"
  - "Inline guard-set update after each create_card prevents duplicates within a single sync run with multiple won deals"
  - "records_synced incremented per auto-created card -- accurate count in SyncLog"

requirements-completed: [TRELLO-03]

# Metrics
duration: 5min
completed: 2026-06-15
---

# Phase 04 Plan 03: Auto-Create Contrato-List Cards for Won Deals Summary

**_make_card_desc writer + sync_trello reconciliation block that creates exactly one Contrato-list card per won Pipedrive deal lacking a linked TrelloCard, with idempotency guard preventing duplicates across sync runs**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-15T04:15:00Z
- **Completed:** 2026-06-15T04:20:15Z
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments

- Added `_make_card_desc(pipedrive_deal_id, extra_desc="")` to `app/services/trello_service.py` -- produces `[seg:deal_id=N]` header that round-trips through `_extract_deal_id_from_desc` (T-04-08 mitigated: only integer in header, no injection surface)
- Added reconciliation block to `sync_trello` in `app/sync/jobs.py` (after the card upsert loop, before success commit): pre-scans `TrelloCard` table for all linked `pipedrive_deal_id_desc` and `deal_id` values, then for each `Deal.status == "won"` not in either set calls `trello.create_card(client, CONTRATO_LIST_ID, deal.title, desc=_make_card_desc(deal.pipedrive_id))` and immediately upserts the new `TrelloCard` row
- Idempotency: guard sets updated inline after each creation so within-run duplicates (multiple won deals) are also caught; across-run duplicates blocked by pre-scan
- Filled in 3 Wave 3 test stubs in `tests/test_trello.py`: `test_card_desc_contains_deal_id`, `test_auto_create_card_for_won_deal`, `test_no_duplicate_card_creation` -- all green
- Full suite: 121 passed, 1 skipped (Wave 4 income projection stub), 0 regressions

## Task Commits

### Task 1: _make_card_desc deal-id header writer (TDD)
1. **RED** -- `ebc983d` `test(04-03): add failing test for _make_card_desc deal-id header writer`
2. **GREEN** -- `ca7dd4f` `feat(04-03): implement _make_card_desc deal-id header writer`

### Task 2: reconciliation step creates cards for won deals (TDD)
3. **RED** -- `4bb3312` `test(04-03): add failing tests for auto-create card reconciliation`
4. **GREEN** -- `a1c467f` `feat(04-03): add reconciliation block to sync_trello for won-deal card creation`

## Files Created/Modified

- `app/services/trello_service.py` -- Added `_make_card_desc(pipedrive_deal_id, extra_desc="")` (21 lines including docstring)
- `app/sync/jobs.py` -- Added reconciliation block (57 lines) inside `sync_trello` try block after initial `db.commit()`
- `tests/test_trello.py` -- 3 Wave 3 stubs implemented (`test_card_desc_contains_deal_id`, `test_auto_create_card_for_won_deal`, `test_no_duplicate_card_creation`); `pytest.skip` removed from all three

## Decisions Made

- `_make_card_desc` uses `f"[seg:deal_id={pipedrive_deal_id}]"` with an integer argument -- the f-string cannot be injected with arbitrary text since Python coerces the integer to digits only (T-04-08 mitigated). Matches `_DEAL_ID_RE = re.compile(r"\[seg:deal_id=(\d+)\]")` exactly.
- Idempotency guard uses two pre-scanned sets (one from `TrelloCard.pipedrive_deal_id_desc`, one from `TrelloCard.deal_id`) -- either match skips creation. This handles the edge case where a card was synced from Trello before the `pipedrive_deal_id_desc` was populated.
- Guard sets updated inline after `db.add(new_card)` so multiple won deals in one sync run do not create duplicate API calls.
- Error handling: the reconciliation block is inside the existing `except Exception` try, so a `create_card` HTTP error is captured as `str(exc)` only and sets `sync_log.status = "error"` -- never leaks auth params.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing update_time in test seed data**
- **Found during:** Task 2 RED phase
- **Issue:** `deals.update_time` column has a NOT NULL constraint; test-seeded `won_deal` objects omitted `update_time` causing IntegrityError
- **Fix:** Added `update_time` and `add_time` to both won_deal seeds in tests
- **Files modified:** `tests/test_trello.py`
- **Commit:** Within `4bb3312`

## Known Stubs

The following test stub remains intentionally skipped (Wave 4 strategy):

| Test | File | Wave |
|------|------|------|
| test_income_projection_math | tests/test_trello.py | Wave 4 (Plan 04-04) |

## Threat Surface Scan

No new network endpoints introduced. All threat mitigations applied:

| Threat | Status |
|--------|--------|
| T-04-07: Write amplification via duplicate card POST | Mitigated: two-set idempotency guard (pipedrive_deal_id_desc + deal_id) |
| T-04-08: Tampering via malformed desc marker | Mitigated: `_make_card_desc` uses integer arg only in f-string header |
| T-04-09: Info disclosure via error path | Mitigated: reconciliation inside existing try/except; str(exc) only |

## Self-Check

- [x] `app/services/trello_service.py` exists with `_make_card_desc` at line 125
- [x] `app/sync/jobs.py` reconciliation block with `trello.create_card` and `trello.CONTRATO_LIST_ID`
- [x] `tests/test_trello.py` Wave 3 stubs green (121 passed, 1 skipped full suite)
- [x] All commits exist: ebc983d, ca7dd4f, 4bb3312, a1c467f

## Self-Check: PASSED

---
*Phase: 04-trello-integration-collection-automation*
*Completed: 2026-06-15*
