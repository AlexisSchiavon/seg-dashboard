---
phase: 04-trello-integration-collection-automation
plan: 04
subsystem: services, schemas, routers, frontend
tags: [trello, income-projection, payment-calendar, deals, dashboard, tdd, dash-02]

# Dependency graph
requires:
  - phase: 04-02
    provides: trello_service.py (resolve_collection_date, _normalize, fuzzy helpers), TrelloCard model, sync job
  - phase: 04-01
    provides: TrelloCard SQLAlchemy model, trello.py wrapper
  - phase: 02
    provides: TalentDetail schema baseline, get_talent_detail endpoint, kpi_service
provides:
  - app/services/trello_service.py (income_projection, payment_calendar, deals_for_talent)
  - app/schemas/dashboard.py (MonthProjection, CalendarEntry, DealRow + extended TalentDetail)
  - app/routers/dashboard.py (get_talent_detail extended with three new Optional fields)
  - frontend/js/dashboard.js (renderTopCampaigns and renderCampaignTable wired to data.deals)
affects:
  - Human verification: Por talento tab (Task 4 — CHECKPOINT PENDING)

# Tech tracking
tech-stack:
  added: []  # Zero new packages (T-04-SC: no installs this phase)
  patterns:
    - "4-month sliding window with divmod month arithmetic (_sliding_window_months)"
    - "income_projection returns list of 4 dicts regardless of card density"
    - "deals_for_talent: linked cards first (list_state from TrelloCard), then unlinked (lost=perdido, others=ejecucion)"
    - "TalentDetail Optional fields default None — backward compatible with pre-Trello tests"
    - "getDealBadge(listState) maps ejecucion/cobranza/cerrado/perdido to sbadge CSS class"
    - "escHtml applied to all deal.title strings before DOM insertion (T-04-11 / CR-02)"

key-files:
  created: []
  modified:
    - app/services/trello_service.py
    - app/schemas/dashboard.py
    - app/routers/dashboard.py
    - frontend/js/dashboard.js
    - tests/test_trello.py
    - tests/test_dashboard.py

key-decisions:
  - "income_projection uses deal.value (venta_total per D-47), not commission_amount"
  - "payment_calendar amount = cobrado + proyeccion + pendiente (total expected per month per UI-SPEC)"
  - "deals_for_talent includes unlinked lost deals as list_state=perdido; open/won unlinked default to ejecucion"
  - "TalentDetail income_projection/payment_calendar/deals are Optional[list] = None — not empty lists — to distinguish no-data from empty-window"
  - "renderTopCampaigns sorts by amount descending in the frontend (slice().sort()) before taking top 3"
  - "getDealBadge maps cerrado to sbadge.cobrado (per UI-SPEC badge variant table)"

# Metrics
duration: ~25min
completed: 2026-06-15
status: CHECKPOINT_PENDING (Task 4 awaits human visual verification)
---

# Phase 04 Plan 04: DASH-02 Revenue Projection Dashboard Slice Summary

**Income projection math (4-month window), extended TalentDetail schema/endpoint, and frontend render functions wired to individual deal data — Por talento tab now serves real Trello+Pipedrive data**

## Status

Tasks 1-3 complete and committed. **Task 4 (visual verification) is a human checkpoint — see checkpoint section below.**

## Performance

- **Duration:** ~25 min (Tasks 1-3)
- **Completed:** 2026-06-15
- **Tasks:** 3 of 4 (Task 4 pending human-verify)
- **Files modified:** 6

## Accomplishments

### Task 1 — projection + calendar + deals service functions

- Added `_month_label(d)` returning `"Mon YYYY"` using `calendar.month_abbr` (English 3-letter, locale-independent per Pitfall 3)
- Added `_sliding_window_months(anchor)` returning 4 first-of-month dates using divmod month arithmetic (handles Dec to Jan year overflow)
- Implemented `income_projection(db, talent_id)`: 4-entry list `{month, cobrado, proyeccion, pendiente}` — groups by resolved `collection_date` month, excludes out-of-window cards, uses `deal.value` (venta_total per D-47)
- Implemented `payment_calendar(db, talent_id)`: 4-entry list `{month, amount}` summing all three layers per month
- Implemented `deals_for_talent(db, talent_id)`: TrelloCard-linked deals (list_state from card) + unlinked deals (lost=perdido, others=ejecucion), sorted by amount descending
- TDD RED commit `599912b` then GREEN commit `e36c915`; `test_income_projection_math` passes (1 test)

### Task 2 — extend TalentDetail schema and endpoint

- Added `MonthProjection`, `CalendarEntry`, `DealRow` Pydantic BaseModel classes to `app/schemas/dashboard.py`
- Extended `TalentDetail` with three `Optional` fields (`income_projection`, `payment_calendar`, `deals`) defaulting to `None` — existing tests unaffected (Pitfall 4)
- Updated `app/routers/dashboard.py`: imported `trello_service` + 3 new schema classes; wired `income_projection()`, `payment_calendar()`, `deals_for_talent()` calls inside `get_talent_detail()`
- TDD RED commit `df4dac1` then GREEN commit `f3fb6f7`
- 2 new tests: `test_talent_detail_includes_income_projection` and `test_talent_detail_no_trello_data_returns_null_fields`
- Full suite: 124 passed, 0 skipped, 0 regressions (was 121)

### Task 3 — wire frontend render functions to deal data

- Added `getDealBadge(listState)` mapping `ejecucion/cobranza/cerrado/perdido` to `.sbadge` CSS class and display label (per UI-SPEC badge variant table)
- Added `dealStateColor(listState)` for `.ctable-icon` dot color
- Updated `renderTopCampaigns(deals)`: accepts `Array<{title, amount, list_state}>`, sorts by amount desc, slices top 3, renders medal cards with `escHtml(deal.title)` (T-04-11)
- Updated `renderCampaignTable(deals, lostOpps)`: accepts individual deal rows; derives `.sbadge` class from `list_state`; wraps all titles in `escHtml` (CR-02)
- Updated `loadTalentDetail`: replaced `const activeStages = (data.funnel||[]).filter(s=>s.count>0)` with `const activeDeals = data.deals || []`
- `renderIncomeProjection` and `renderPaymentCalendar` left unchanged (already wired to `data.income_projection` and `data.payment_calendar`)
- `node --check` passes; commit `485b0de`

## Task Commits

1. **Task 1 RED: add failing test** - `599912b` (test)
2. **Task 1 GREEN: implement service functions** - `e36c915` (feat)
3. **Task 2 RED: add failing tests** - `df4dac1` (test)
4. **Task 2 GREEN: extend schema and endpoint** - `f3fb6f7` (feat)
5. **Task 3: wire frontend render functions** - `485b0de` (feat)

## Files Created/Modified

- `app/services/trello_service.py` — added `_month_label`, `_sliding_window_months`, `income_projection`, `payment_calendar`, `deals_for_talent` (+160 lines)
- `app/schemas/dashboard.py` — added `MonthProjection`, `CalendarEntry`, `DealRow`; extended `TalentDetail` with 3 Optional fields (+25 lines)
- `app/routers/dashboard.py` — imported trello_service + new schema types; wired 3 service calls in `get_talent_detail` (+15 lines)
- `frontend/js/dashboard.js` — added `getDealBadge`, `dealStateColor`; rewrote `renderTopCampaigns`, `renderCampaignTable`; updated `loadTalentDetail` (+75/-20 lines)
- `tests/test_trello.py` — replaced `pytest.skip` stub with 80-line concrete test for `income_projection_math`
- `tests/test_dashboard.py` — added `test_talent_detail_includes_income_projection` and `test_talent_detail_no_trello_data_returns_null_fields`

## Decisions Made

- `income_projection` uses `deal.value` (venta_total per D-47), not `commission_amount`
- `payment_calendar` amount = cobrado + proyeccion + pendiente (total expected per month)
- TrelloCards outside the 4-month window are excluded (not bucketed into nearest month)
- `TalentDetail` new fields are `Optional[list] = None`, not empty lists — `None` signals "no Trello data" vs `[]` which would mean "data fetched but empty"
- `getDealBadge` maps `cerrado` to `sbadge.cobrado` (not `sbadge.cerrado`) per UI-SPEC badge variant table
- `deals_for_talent` includes all talent deals (linked + unlinked), so the campaign table shows the complete picture even before Trello sync completes

## Deviations from Plan

None — plan executed exactly as written for Tasks 1-3.

## Checkpoint Pending

Task 4 is a `checkpoint:human-verify` gate. Visual inspection of the Por talento tab required before this plan is marked complete.

## Known Stubs

None. All data paths are fully wired — the frontend renders from real data returned by the extended endpoint. Empty-state placeholders render correctly when `data.deals` is null or empty.

## Threat Surface Scan

No new network endpoints introduced. Threat mitigations applied as planned:

| Threat | Status |
|--------|--------|
| T-04-10: Unauthenticated access to get_talent_detail | Inherited router-level `get_current_user` dependency |
| T-04-11: XSS via deal title strings | `escHtml()` applied to `deal.title` in both `renderTopCampaigns` and `renderCampaignTable` |
| T-04-12: Raw DB row leakage | `response_model=TalentDetail` + explicit typed schema classes (MonthProjection, CalendarEntry, DealRow) |
| T-04-13: talent_id path param tampering | FastAPI coerces to int (422 on non-int); 404 via `db.get(Talent, talent_id)` guard |

## Self-Check

- [x] `app/services/trello_service.py` contains `def income_projection(`, `def payment_calendar(`, `def deals_for_talent(`
- [x] `app/schemas/dashboard.py` contains `class MonthProjection`, `class CalendarEntry`, `class DealRow`
- [x] `TalentDetail` declares `income_projection`, `payment_calendar`, `deals` with `None` default
- [x] `app/routers/dashboard.py` contains `income_projection` call
- [x] `frontend/js/dashboard.js` contains `data.deals` passed to render functions
- [x] `node --check frontend/js/dashboard.js` exits 0
- [x] `python3 -m pytest tests/test_trello.py -k income_projection_math -x -q` passes (1 passed)
- [x] `python3 -m pytest tests/test_dashboard.py -k talent_detail -x -q` passes (5 passed)
- [x] `python3 -m pytest -q` full suite passes (124 passed, 0 skipped)

## Self-Check: PASSED
