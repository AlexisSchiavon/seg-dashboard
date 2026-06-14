---
phase: 02-pipedrive-integration-core-dashboard
plan: 02
subsystem: api, ui, database
tags: [fastapi, sqlalchemy, sqlite, pydantic, vanilla-js, dashboard, kpis, funnel]

requires:
  - phase: 02-01
    provides: Deal/DealStageEvent/SyncLog ORM models + 476 synced deals + sync endpoint + dashboard shell HTML/CSS/JS

provides:
  - "GET /dashboard/summary: global KPI tiles + talent ranking + activity feed (auth-protected, Pydantic-validated)"
  - "GET /dashboard/funnel: 6-stage PIPE-05 funnel with bottleneck detection (auth-protected)"
  - "app/services/kpis.py: global_kpis() + talent_ranking() with Sin-talento bucket (Pitfall 4)"
  - "app/services/funnel.py: funnel_overview() 6-stage aggregation + bottleneck heuristic + recent_activity()"
  - "app/schemas/dashboard.py: DashboardSummary, FunnelOverview, KpiTile, RankingRow, ActivityItem, BottleneckInfo, StageBucket"
  - "Resumen tab: live KPI grid (Pipeline total accent + amber/purple/green tiles), talent ranking with Sin-talento row, activity feed"
  - "Funnel tab: 6 funnel bars + bottleneck alert (warn) or insufficient-data alert (info)"
  - "26 new tests (test_kpis.py 8, test_funnel.py 8, test_dashboard.py 10); full suite 57/57 green"

affects:
  - 02-03 (Por talento tab — builds on same services/schemas layer)
  - 05-ai-reports (consumes kpis/funnel services for AI narration)
  - 06-nl-agent (reads from same service layer)

tech-stack:
  added: []
  patterns:
    - "Service layer pattern: kpis.py/funnel.py are plain db:Session-first functions; Depends() stays in the router"
    - "Pitfall 4 query split: global KPIs query Deal directly (no Talent join); Sin-talento bucket via separate Deal.talent_id.is_(None) query"
    - "PIPE-05 canonical stages: STAGES constant in funnel.py — always emit all 6 even with 0 count"
    - "Bottleneck heuristic: cumulative-ratio snapshot over STAGES list; insufficient_data=True when total deals < 10"
    - "Router pattern: APIRouter(dependencies=[Depends(get_current_user)]) matches talents.py convention"
    - "Empty state gate: has_data=False returned from endpoint when Deal count == 0"
    - "TDD RED/GREEN commit sequence: test commit (67c3eb9) before feat commit (9ee255a)"

key-files:
  created:
    - app/services/kpis.py
    - app/services/funnel.py
    - app/schemas/dashboard.py
    - app/routers/dashboard.py
    - tests/test_kpis.py
    - tests/test_funnel.py
    - tests/test_dashboard.py
  modified:
    - app/main.py (added dashboard.router include before static mount)
    - frontend/index.html (Resumen + Funnel tab containers with stable IDs)
    - frontend/js/dashboard.js (loadSummary/loadFunnel + all render functions)

key-decisions:
  - "Empty state driven by Deal count == 0 (not by SyncLog presence) — simpler, robust to manual seed"
  - "Bottleneck uses cumulative snapshot ratio over STAGES order, not pair-wise delta — consistent with RESEARCH.md Pattern 4"
  - "frontend/css/styles.css had all required component classes from Plan 02-01; no CSS additions needed in this plan"
  - "loadSummary() called on DOMContentLoaded AND on Resumen tab activation to keep data fresh after sync"

patterns-established:
  - "Service layer functions take db:Session as first arg — routers wire Depends(get_db)"
  - "All 6 STAGES always emitted by funnel_overview() even at zero count — prevents frontend null checks"
  - "Sin-talento bucket appended last in ranking only when count > 0 (no ghost row)"

requirements-completed: [DASH-01, DASH-03]

duration: 30min
completed: 2026-06-14
---

# Phase 02 Plan 02: Resumen + Funnel Dashboard Summary

**Read-layer services and live dashboard rendering: global KPI tiles, Sin-talento ranking bucket, 6-stage funnel with bottleneck detection, and activity feed from synced Pipedrive data**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-06-14T19:56:00Z
- **Completed:** 2026-06-14T20:30:00Z
- **Tasks:** 3 auto tasks complete (Task 4 = checkpoint:human-verify, pending)
- **Files modified:** 10

## Accomplishments

- Created `app/services/kpis.py` + `app/services/funnel.py` with correct Pitfall-4 query split: global totals include `talent_id IS NULL` deals; per-talent ranking uses outerjoin + separate `Sin talento asignado` bucket appended last
- Built auth-protected `/dashboard/summary` and `/dashboard/funnel` endpoints returning Pydantic-validated `DashboardSummary` / `FunnelOverview` response models; wired into `app/main.py` before the static mount
- Extended `frontend/index.html` and `frontend/js/dashboard.js` with `loadSummary()` / `loadFunnel()` rendering all 6 PIPE-05 funnel stages, KPI grid with single accent tile (Pipeline total), talent ranking with medal classes, activity feed, and the exact UI-SPEC bottleneck copy — no "industria" text anywhere
- 57/57 tests pass (26 new tests: 8 in test_kpis.py, 8 in test_funnel.py, 10 in test_dashboard.py)

## Task Commits

1. **test(02-02): add failing tests for kpis/funnel services (RED)** - `67c3eb9`
2. **feat(02-02): Task 1 - global KPI/funnel/activity services with Pydantic schemas** - `9ee255a`
3. **feat(02-02): Task 2 - dashboard router + main.py wiring** - `a802de7`
4. **feat(02-02): Task 3 - Resumen + Funnel tab rendering (HTML/CSS/JS)** - `bce8763`

## Files Created/Modified

- `app/services/kpis.py` - global_kpis() (4 KPI tiles), talent_ranking() with Sin-talento bucket
- `app/services/funnel.py` - funnel_overview() 6-stage PIPE-05 + bottleneck heuristic, recent_activity()
- `app/schemas/dashboard.py` - DashboardSummary, FunnelOverview, KpiTile, RankingRow, ActivityItem, BottleneckInfo, StageBucket
- `app/routers/dashboard.py` - GET /dashboard/summary + GET /dashboard/funnel, auth-protected, response_model validated
- `app/main.py` - Added dashboard.router include before static mount
- `tests/test_kpis.py` - 8 tests: commission calc, Sin-talento inclusion, ranking bucket, per-KPI assertions
- `tests/test_funnel.py` - 8 tests: 6-stage mapping, zero-count stages, bottleneck detection, activity order/limit
- `tests/test_dashboard.py` - 10 tests: 401 auth guard, empty state, shape validation, Pitfall-4 reconciliation, bottleneck with large dataset
- `frontend/index.html` - Resumen tab containers (kpi-grid, ranking-list, activity-list) + Funnel tab (funnel-rows, bottleneck-slot)
- `frontend/js/dashboard.js` - loadSummary/loadFunnel + renderKpis/renderRanking/renderActivity/renderFunnel/renderBottleneck

## Decisions Made

- Empty state gated on `Deal count == 0` (simpler than checking SyncLog presence; handles manually seeded DBs)
- Bottleneck uses cumulative snapshot ratios: `deals_at_or_after(stage i+1) / deals_at_or_after(stage i)` — matches RESEARCH.md Pattern 4 and gives meaningful conversion even when stages aren't strictly sequential
- CSS did not need any additions: Plan 02-01 already ported all required component classes from the mockup with correct UI-SPEC deviations (kpi-val 500, card 16px)
- `loadSummary()` called both on DOMContentLoaded and on Resumen tab activation so data refreshes after a sync without requiring a full page reload

## Deviations from Plan

None — plan executed exactly as written. The CSS already had all required classes from Plan 02-01; no CSS additions were needed (plan anticipated this possibility).

## Issues Encountered

None. TDD RED/GREEN cycle executed cleanly: tests failed on import (services not yet created), then passed after implementation.

## Known Stubs

None. All data is sourced from the live SQLite Deal/DealStageEvent tables populated by the Plan 02-01 sync. The "En ejecución" and "Cobranza" funnel stages show count=0 intentionally until Phase 4 (Trello integration) — this is documented behavior (PIPE-05), not a stub.

## Threat Flags

No new threat surface introduced beyond the plan's registered threats (T-02B-01 through T-02B-04). All mitigated per plan:
- T-02B-01: `dependencies=[Depends(get_current_user)]` on router + test_summary_requires_auth / test_funnel_requires_auth assert 401
- T-02B-02: `response_model=DashboardSummary` / `response_model=FunnelOverview` on both endpoints

## User Setup Required

None — builds on existing Pipedrive sync from Plan 02-01. No new environment variables or external service configuration.

## Next Phase Readiness

- Plan 02-03 (Por talento tab) can build directly on `app/services/kpis.py` and `app/services/funnel.py` — both accept `talent_id` filter extensions
- `/dashboard/summary` and `/dashboard/funnel` are live and auth-protected; human verification (Task 4) pending
- Checkpoint: human must confirm KPIs add up, single accent tile, 6 stages in order, bottleneck copy correct before proceeding to 02-03

---
*Phase: 02-pipedrive-integration-core-dashboard*
*Completed: 2026-06-14*
