---
phase: 03-google-sheets-leads-integration
plan: "03"
subsystem: dashboard-leads-kpis
tags: [dashboard, leads, kpis, frontend, tdd]
dependency_graph:
  requires:
    - "03-01"  # leads_summary() service + Lead model
    - "03-02"  # leads_list + Leads tab UI (fixtures reused in tests)
  provides:
    - GET /dashboard/summary now returns leads_totales + calificados
    - Resumen tab "Leads totales" and "Calificados" KPI tiles wired with real counts
  affects:
    - app/schemas/dashboard.py
    - app/routers/dashboard.py
    - frontend/index.html
    - frontend/js/dashboard.js
    - tests/test_dashboard.py
tech_stack:
  added: []
  patterns:
    - DashboardSummary schema extension with default-0 int fields
    - Router calls service before has_data branch to populate independent counts
    - textContent rendering for integer KPI tile values (T-03C-03)
key_files:
  created: []
  modified:
    - app/schemas/dashboard.py
    - app/routers/dashboard.py
    - frontend/index.html
    - frontend/js/dashboard.js
    - tests/test_dashboard.py
decisions:
  - leads_service.leads_summary(db) called before _has_data(db) check so counts populate on both return paths
  - leads-overview-grid is a separate section from the deal kpi-grid (independent data source)
  - textContent used (not innerHTML) for integer tile values (T-03C-03 mitigated)
  - Nullish-coalescing defaults (??0) guard against older API responses in JS
metrics:
  duration: "3 minutes"
  completed: "2026-06-14"
  tasks_completed: 2
  files_modified: 5
  tests_added: 3
  tests_total: 111
---

# Phase 03 Plan 03: Resumen Tab Leads KPI Tiles Summary

**One-liner:** Extended DashboardSummary with leads_totales + calificados from leads_summary(), wired into the Resumen tab as two new KPI tiles rendered via renderLeadsOverviewKpis().

## What Was Built

### Task 1: Extend DashboardSummary schema + get_summary with leads KPIs

Extended `app/schemas/dashboard.py` to add `leads_totales: int = 0` and `calificados: int = 0` to the `DashboardSummary` model. Updated `app/routers/dashboard.py` to import `leads_service` and call `leads_service.leads_summary(db)` before the `_has_data` branch, passing both fields into both return paths. This ensures leads counts appear on the Resumen tab regardless of whether Pipedrive sync has run.

**TDD sequence:**
- RED: 3 failing tests asserting `leads_totales` and `calificados` in `/dashboard/summary` response (commit c3703db)
- GREEN: Schema + router implementation — all 3 pass, 111 total passing (commit 7665d75)

### Task 2: Resumen tab Leads tiles + dashboard.js rendering

Added a new `leads-overview-grid` section to `#page-overview` in `frontend/index.html` with two tiles:
- "Leads totales" (variant blue, `id="leads-totales-val"`)
- "Calificados" (variant green, `id="calificados-val"`)

Added `renderLeadsOverviewKpis(leadsTotales, calificados)` to `frontend/js/dashboard.js` that sets both tile values via `textContent` (not innerHTML, per T-03C-03). Wired the call before the `has_data` branch in `loadSummary()` with `data.leads_totales ?? 0` and `data.calificados ?? 0` so tiles show 0 (not "--" or "undefined") on both the empty-state and data-loaded paths (commit 1bcec2a).

## Commits

| Task | Hash | Message |
|------|------|---------|
| Task 1 RED | c3703db | test(03-03): add failing tests for leads KPIs on GET /dashboard/summary |
| Task 1 GREEN | 7665d75 | feat(03-03): extend DashboardSummary schema and get_summary with leads KPIs |
| Task 2 | 1bcec2a | feat(03-03): Resumen tab Leads tiles + renderLeadsOverviewKpis wiring |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — `leads-totales-val` and `calificados-val` tiles are wired to real data from `leads_service.leads_summary(db)`. The "--" placeholder in HTML is only shown before the first `loadSummary()` call (which fires on DOMContentLoaded), and is immediately replaced with live integer counts.

## Threat Flags

No new security-relevant surface introduced beyond what the plan's threat model describes. All three registered threats (T-03C-01, T-03C-02, T-03C-03) were mitigated:
- T-03C-01: Inherited `dependencies=[Depends(get_current_user)]` on the router — confirmed endpoint returns 401 without JWT (existing test suite covers this).
- T-03C-02: Only aggregate integer counts cross to client — no PII (email/asunto) in DashboardSummary.
- T-03C-03: `renderLeadsOverviewKpis` uses `textContent` not `innerHTML`.

## TDD Gate Compliance

- RED gate commit: c3703db (test(03-03): ...)
- GREEN gate commit: 7665d75 (feat(03-03): ...)
- No REFACTOR needed — implementation was clean as written.

## Self-Check: PASSED

- [x] app/schemas/dashboard.py modified — FOUND
- [x] app/routers/dashboard.py modified — FOUND
- [x] frontend/index.html modified — FOUND
- [x] frontend/js/dashboard.js modified — FOUND
- [x] tests/test_dashboard.py modified — FOUND
- [x] c3703db exists in git log
- [x] 7665d75 exists in git log
- [x] 1bcec2a exists in git log
- [x] 111 tests passing (full suite green)
