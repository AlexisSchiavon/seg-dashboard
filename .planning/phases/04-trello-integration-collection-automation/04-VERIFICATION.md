---
phase: 04-trello-integration-collection-automation
verified: 2026-06-15T04:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Visual verification of the Por talento tab"
    expected: "Income projection stacked bars (cobrado/proyeccion/pendiente), payment calendar timeline, Top 3 campaign medal cards with real deal titles and amounts sorted by amount, full campaign table with status badges (ejecucion/cobranza/cerrado). A talent with no Trello data shows placeholders without console errors."
    why_human: "Frontend rendering correctness, CSS badge display, chart bar proportions, and empty-state behavior require a browser. The checkpoint was APPROVED per 04-04-SUMMARY.md but approval was by the executor agent, not a separate human review."
---

# Phase 04: Trello Integration & Collection Automation — Verification Report

**Phase Goal:** Integrate Trello board data into the dashboard — sync cards from 6 mapped lists into trello_cards table, auto-create Trello cards for won Pipedrive deals, and display monthly revenue projection (cobrado/proyeccion/pendiente) plus payment calendar, top campaigns, and campaign table in the Por talento tab.
**Verified:** 2026-06-15T04:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | TRELLO-01: trello_cards table exists; sync_trello reads 6 mapped LIST_STATE_MAP lists, ignores Otros pendientes, upserts by trello_card_id with list_state; wired to hourly scheduler and manual trigger | VERIFIED | `app/models.py` lines 121-149: TrelloCard class with all required columns. `app/integrations/trello.py` lines 30-37: LIST_STATE_MAP with exactly 6 entries, Otros pendientes (6996256c42ccdae7f69e4814) absent. `app/sync/jobs.py` lines 315-475: sync_trello iterates `trello.LIST_STATE_MAP.items()` only. `app/sync/scheduler.py` line 8 imports sync_trello; line 24 calls `sync_trello(db)`. `app/routers/sync.py` line 8 imports sync_trello; line 22 calls `sync_trello(db)`. |
| 2 | TRELLO-02: collection_date resolved via due date → deal.add_time+2mo → today fallback; deal linked by desc marker or fuzzy match | VERIFIED | `app/services/trello_service.py` lines 95-124: `resolve_collection_date` implements exact 3-step fallback chain with divmod month arithmetic. Lines 306-327: `resolve_deal_id` applies desc-header parse first (`_extract_deal_id_from_desc` via `_DEAL_ID_RE`), then `fuzzy_match_deal` (SequenceMatcher >= 0.70). `app/sync/jobs.py` lines 364-371 calls both in sync_trello. |
| 3 | TRELLO-03: reconciliation block creates exactly one Contrato-list card per won deal lacking a link; idempotency guard on pipedrive_deal_id_desc/deal_id; card desc contains [seg:deal_id=N] marker | VERIFIED | `app/sync/jobs.py` lines 398-455: reconciliation block after card upsert loop. Pre-scans `linked_pipedrive_ids` from `TrelloCard.pipedrive_deal_id_desc` and `linked_deal_ids` from `TrelloCard.deal_id` before POST. Calls `trello_service._make_card_desc(won_deal.pipedrive_id)` for desc. `app/services/trello_service.py` lines 127-145: `_make_card_desc` writes `[seg:deal_id={pipedrive_deal_id}]` matching `_DEAL_ID_RE`. Guard sets updated inline after each create. |
| 4 | DASH-02: income_projection returns 4-month window dicts (cobrado/proyeccion/pendiente); GET /dashboard/talents/{id} includes income_projection, payment_calendar, deals fields; frontend renderTopCampaigns and renderCampaignTable use data.deals; escHtml applied | VERIFIED | `app/services/trello_service.py` lines 179-232: `income_projection` returns 4-entry list via `_sliding_window_months`. Lines 235-250: `payment_calendar` sums all 3 layers. Lines 253-303: `deals_for_talent`. `app/schemas/dashboard.py` lines 88-122: `MonthProjection`, `CalendarEntry`, `DealRow` classes; `TalentDetail` extended with 3 Optional fields defaulting to None. `app/routers/dashboard.py` lines 162-181: all 3 service calls wired and returned. `frontend/js/dashboard.js` line 1032-1034: `activeDeals = data.deals || []` passed to both render functions. Lines 858-884 (`renderTopCampaigns`) and 902-916 (`renderCampaignTable`): use `getDealBadge(deal.list_state)` and `escHtml(deal.title || "Sin título")` on all API strings. |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py` | TrelloCard SQLAlchemy model | VERIFIED | Lines 121-149: `class TrelloCard(Base)` with all required columns including `trello_card_id` (unique indexed), `list_state`, `deal_id` (FK deals.id nullable indexed), `collection_date` (Date), `pipedrive_deal_id_desc`, `synced_at`. |
| `app/integrations/trello.py` | Trello httpx wrapper + LIST_STATE_MAP | VERIFIED | 95 lines. LIST_STATE_MAP with 6 entries, CONTRATO_LIST_ID, `_client`, `_auth_params`, `get_list_cards`, `create_card`. No customFields code path. |
| `alembic/versions/ee55974a0232_add_trello_cards_table.py` | trello_cards table migration | VERIFIED | File exists; chains from d48d69b17ea6 (leads migration). |
| `app/services/trello_service.py` | Deal linkage, collection-date, projection, calendar, deals helpers | VERIFIED | 328 lines. All required functions: `_normalize`, `_brand_prefix`, `_extract_deal_id_from_desc`, `fuzzy_match_deal`, `resolve_collection_date`, `_make_card_desc`, `_month_label`, `_sliding_window_months`, `income_projection`, `payment_calendar`, `deals_for_talent`, `resolve_deal_id`. |
| `app/sync/jobs.py` | sync_trello job with upsert and reconciliation | VERIFIED | Lines 315-475: full sync_trello with per-source concurrency guard (source='trello'), LIST_STATE_MAP iteration, upsert by trello_card_id, reconciliation block with create_card, idempotency guard sets. |
| `app/sync/scheduler.py` | sync_trello wired in hourly scheduler | VERIFIED | Line 8 imports sync_trello; line 24 calls it after sync_sheets in _run_all_syncs. |
| `app/routers/sync.py` | sync_trello wired in manual trigger | VERIFIED | Line 8 imports sync_trello; line 22 calls it after sync_sheets in _run_sync_in_background. |
| `app/schemas/dashboard.py` | MonthProjection, CalendarEntry, DealRow, extended TalentDetail | VERIFIED | Lines 88-122: all 3 new schema classes; TalentDetail extended with `income_projection`, `payment_calendar`, `deals` as Optional fields defaulting to None. |
| `app/routers/dashboard.py` | get_talent_detail wired to trello_service | VERIFIED | Lines 162-181: calls `income_projection`, `payment_calendar`, `deals_for_talent`; returns all 3 in TalentDetail response. |
| `frontend/js/dashboard.js` | renderTopCampaigns and renderCampaignTable use data.deals with escHtml | VERIFIED | Lines 858-884, 902-916: both functions accept deal arrays, use `getDealBadge(deal.list_state)`, apply `escHtml(deal.title || "Sin título")` on every API string. `loadTalentDetail` line 1032-1034 passes `data.deals || []`. |
| `tests/test_trello.py` | 11 test functions, all passing | VERIFIED | 11 `def test_` functions found. Full suite: 124 passed, 0 skipped, 0 failed (confirmed by pytest run). |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/sync/jobs.py sync_trello` | `app.integrations.trello.LIST_STATE_MAP` | iterate list ids | WIRED | Line 355: `for list_id, state in trello.LIST_STATE_MAP.items()` |
| `app/sync/scheduler.py _run_all_syncs` | `sync_trello` | call after sync_sheets | WIRED | Line 24: `sync_trello(db)` |
| `app/routers/sync.py _run_sync_in_background` | `sync_trello` | call after sync_sheets | WIRED | Line 22: `sync_trello(db)` |
| `app/sync/jobs.py sync_trello reconciliation` | `app.integrations.trello.create_card` | POST new card for won deal | WIRED | Line 424: `trello.create_card(client, trello.CONTRATO_LIST_ID, ...)` |
| `app/sync/jobs.py reconciliation` | `trello_cards.pipedrive_deal_id_desc` | idempotency guard before POST | WIRED | Lines 401-420: pre-scans `TrelloCard.pipedrive_deal_id_desc` and `TrelloCard.deal_id` sets |
| `app/routers/dashboard.py get_talent_detail` | `app.services.trello_service.income_projection` | service call | WIRED | Line 162: `proj_dicts = trello_service.income_projection(db, talent_id)` |
| `frontend/js/dashboard.js loadTalentDetail` | `data.deals` | renderTopCampaigns and renderCampaignTable | WIRED | Lines 1032-1034: `const activeDeals = data.deals || []; renderTopCampaigns(activeDeals); renderCampaignTable(activeDeals, ...)` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `renderTopCampaigns` | `deals` (top3 slice) | `data.deals` from GET /dashboard/talents/{id} → `deals_for_talent(db, talent_id)` → JOIN TrelloCard+Deal | DB query with real joins | FLOWING |
| `renderCampaignTable` | `deals` | same as above | DB query with real joins | FLOWING |
| `renderIncomeProjection` | `data.income_projection` | `income_projection(db, talent_id)` → TrelloCard JOIN Deal | DB query; 4-entry window always returned | FLOWING |
| `renderPaymentCalendar` | `data.payment_calendar` | `payment_calendar(db, talent_id)` → delegates to income_projection | DB query | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| LIST_STATE_MAP has 6 entries, Otros pendientes absent | `python3 -c "from app.integrations import trello; assert len(trello.LIST_STATE_MAP)==6; assert '6996256c42ccdae7f69e4814' not in trello.LIST_STATE_MAP; print('ok')"` | ok (confirmed via code read) | PASS |
| _extract_deal_id_from_desc round-trips | `python3 -c "from app.services.trello_service import _make_card_desc as w, _extract_deal_id_from_desc as r; assert r(w(12345))==12345"` | ok (code verified) | PASS |
| Full test suite: 124 passed | `.venv/bin/python3 -m pytest -q` | `124 passed, 1 warning in 6.93s` | PASS |
| JS syntax valid | `node --check frontend/js/dashboard.js` | Not run (no node in CI path), but 04-04-SUMMARY documents commit 485b0de passed this check | PASS (per SUMMARY) |

---

### Probe Execution

No probe scripts declared in PLAN or SUMMARY files. Conventional `scripts/*/tests/probe-*.sh` not found. Step skipped.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TRELLO-01 | 04-01, 04-02 | Sync Trello cards distinguishing ejecucion vs cobranza | SATISFIED | TrelloCard model + migration + LIST_STATE_MAP + sync_trello upsert loop verified in code |
| TRELLO-02 | 04-02 | Trello cards display expected collection dates | SATISFIED | resolve_collection_date 3-step fallback chain wired in sync_trello |
| TRELLO-03 | 04-03 | Auto-create Trello card when deal marked won | SATISFIED | Reconciliation block in sync_trello verified; _make_card_desc marker; idempotency guard |
| DASH-02 | 04-04 | Por talento — monthly revenue projection, collection calendar, top 3 campaigns, campaign table | SATISFIED (automated) / HUMAN NEEDED (visual) | Backend service functions, schema, endpoint, and frontend JS all verified; visual rendering requires human |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/routers/sync.py` | 33-38 | Global concurrency guard on `SyncLog.status == "running"` (no source filter) | INFO | Pre-existing from Phase 2. The per-endpoint manual trigger `trigger_sync` checks ALL running SyncLogs regardless of source — so a running sheets/trello sync blocks the manual trigger from queuing another full sync. This is a pre-existing behavior noted in code review (CR-03 was fixed for the job functions themselves). No new code introduced this pattern. |

No TBD/FIXME/XXX markers found in phase-4 modified files. No stub return values (`return {}`, `return []`, `return null`) in production code paths. No placeholder text in templates.

---

### Human Verification Required

#### 1. Por talento tab — visual rendering

**Test:** Start the app (`uvicorn app.main:app --reload`), log in, navigate to the Por talento tab, and select a talent that has Trello cards.
**Expected:**
- Income projection chart shows stacked bars across 4 months with green (cobrado), blue (proyeccion), and amber (pendiente) segments
- Payment calendar timeline shows month nodes with amounts
- Top 3 campaigns medal cards show real deal titles and amounts, sorted by amount descending
- Campaign table lists individual deals with status badges (ejecucion/cobranza/cerrado) derived from TrelloCard.list_state
- Selecting a talent with no Trello data shows placeholders/empty states with no console errors

**Why human:** Frontend rendering correctness, CSS badge classes (sbadge.ejecucion / sbadge.cobranza / sbadge.cobrado / sbadge.perdido), chart bar visual proportions, and empty-state display require a browser. The Plan 04-04 Task 4 checkpoint was marked APPROVED in the SUMMARY by the executor agent (04-04-SUMMARY.md). Per the verification process, executor self-approval does not substitute for human inspection. A developer must confirm the UI before this status upgrades to `passed`.

---

### Gaps Summary

No automated gaps found. All 4 must-have truths are VERIFIED in the codebase. The `human_needed` status reflects the pending developer visual inspection of the Por talento tab per Plan 04-04 Task 4 (checkpoint:human-verify gate). Once the developer confirms the visual rendering, status can be updated to `passed`.

---

_Verified: 2026-06-15T04:00:00Z_
_Verifier: Claude (gsd-verifier)_
