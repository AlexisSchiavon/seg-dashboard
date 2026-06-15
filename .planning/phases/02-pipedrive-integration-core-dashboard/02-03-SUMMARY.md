---
phase: 02-pipedrive-integration-core-dashboard
plan: "03"
subsystem: ui, api, database
tags: [fastapi, sqlite, sqlalchemy, vanilla-js, dark-mode, pipedrive, kpis, funnel, tdd]

# Dependency graph
requires:
  - phase: 02-pipedrive-integration-core-dashboard
    plan: "02"
    provides: "DashboardSummary schema, /dashboard/summary endpoint, Resumen + Funnel tab, base kpis/funnel services"
provides:
  - "talent_detail() service: per-talent KPIs (deals_won, revenue, avg_deal, conv_rate) computed exclusively from a single talent's deals"
  - "talent_funnel() service: 6-stage funnel filtered by talent_id"
  - "4 new Pydantic schemas: TalentDetail, LostOpportunity, LostReasonSummary, BrandCategorySlice"
  - "GET /dashboard/talents/{talent_id} auth-protected endpoint returning TalentDetail (404 on unknown talent)"
  - "Por talento tab: talent selector, KPI cards, per-talent funnel, deals activos table, brand-category donut by deal count, lost opportunities with Spanish-label razón-de-pérdida pills"
  - "Empty-state handling: 'Sin oportunidades perdidas este periodo' and 'Sin categorías de marca registradas todavía'"
affects:
  - 02-04 (Trello integration — may display talent-level data)
  - 03-01 (AI reports — talent_detail service is primary data source for per-talent report sections)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-entity service pattern: talent_detail(db, talent_id) mirrors dashboard_summary(db) shape, enabling consistent service-layer composition"
    - "Loss-reason label resolution: Deal.loss_reason integer IDs resolved to Spanish labels at query time, never exposed to UI as integers"
    - "Brand-category donut: aggregated by deal count (not revenue) using 6 fixed categories, rendered as SVG + legend in vanilla JS"
    - "TDD RED/GREEN: failing tests committed before implementation, all 65 tests passing at plan completion"

key-files:
  created: []
  modified:
    - app/services/kpis.py
    - app/services/funnel.py
    - app/schemas/dashboard.py
    - app/routers/dashboard.py
    - frontend/index.html
    - frontend/css/styles.css
    - frontend/js/dashboard.js
    - tests/test_kpis.py
    - tests/test_funnel.py
    - tests/test_dashboard.py

key-decisions:
  - "Brand-category donut measures % by deal count (not revenue) per D-26/D-27 spec"
  - "Section order in Por talento tab: KPIs → Funnel → Deals activos → Categorías de marca → Oportunidades perdidas (D-28); 'Fuente de leads' excluded from per-talent view"
  - "Loss reason displayed as Spanish label pill, never as raw integer ID"
  - "404 returned (not empty TalentDetail) when talent_id not found in DB"

patterns-established:
  - "Service isolation: talent_detail() never leaks cross-talent data — all DB queries filter by talent_id"
  - "Empty-state strings are defined in JS render functions and shown when API arrays are empty, preventing blank UI panels"

requirements-completed: [DASH-02]

# Metrics
duration: ~90min (across two executor sessions with human checkpoint)
completed: 2026-06-14
---

# Phase 02 Plan 03: Por Talento Tab Summary

**Per-talent dashboard slice: talent_detail() service, /dashboard/talents/{id} auth endpoint, and Por talento tab with KPI cards, 6-stage funnel, brand-category donut by deal count, and Spanish-label lost-opportunity pills.**

## Performance

- **Duration:** ~90 min (two executor sessions, one human checkpoint)
- **Started:** 2026-06-14
- **Completed:** 2026-06-14
- **Tasks:** 4 (RED + Tasks 1-3) + human checkpoint approved
- **Files modified:** 10

## Accomplishments

- talent_detail() service computes per-talent KPIs (deals_won, revenue, avg_deal_size, conversion_rate) exclusively from deals belonging to a single talent_id, with no cross-talent data leakage
- GET /dashboard/talents/{talent_id} auth-protected FastAPI endpoint returns TalentDetail schema; responds 404 for unknown talent IDs
- Por talento tab renders talent selector, KPI cards, 6-stage funnel bars, deals activos table, brand-category donut (% by deal count, 6 categories), and oportunidades perdidas list with Spanish razón-de-pérdida label pills — D-28 section order enforced
- Full TDD RED/GREEN cycle: 65/65 tests passing; human checkpoint verified tab layout and behavior in browser

## Task Commits

Each task was committed atomically:

1. **RED: Failing tests for per-talent KPIs/funnel/lost-opps** - `74f46fc` (test)
2. **Task 1: talent_detail() service + 4 schemas** - `0538ffe` (feat)
3. **Task 2: GET /dashboard/talents/{id} endpoint + contract tests** - `77c397c` (feat)
4. **Task 3: Por talento tab rendering** - `5f2280d` (feat)
5. **Task 4 (checkpoint): Human verification — approved** - no code commit (user approval)

## Files Created/Modified

- `app/services/kpis.py` - Added talent_detail(db, talent_id) returning TalentDetail with per-talent KPIs, lost-opp grouping, brand-category donut slices
- `app/services/funnel.py` - Added talent_funnel(db, talent_id) filtering 6-stage funnel by talent
- `app/schemas/dashboard.py` - Added TalentDetail, LostOpportunity, LostReasonSummary, BrandCategorySlice Pydantic schemas
- `app/routers/dashboard.py` - Added GET /dashboard/talents/{talent_id} auth-protected endpoint
- `frontend/index.html` - Added Por talento tab panel with talent selector, KPI section, funnel, deals table, donut, lost-opps sections in D-28 order
- `frontend/css/styles.css` - Added CSS classes for talent tab layout, donut, label pills, empty states
- `frontend/js/dashboard.js` - Added loadTalentDetail(id), renderTalentKPIs(), renderTalentFunnel(), renderBrandDonut(), renderLostOpportunities(), talent selector event wiring
- `tests/test_kpis.py` - Per-talent KPI unit tests
- `tests/test_funnel.py` - talent_funnel() unit tests
- `tests/test_dashboard.py` - GET /dashboard/talents/{id} contract tests (auth, 200, 404)

## Decisions Made

- Brand-category donut aggregates by deal count (not revenue) per D-26/D-27 spec — revenue donut is explicitly out of scope for this plan
- D-28 section order (KPIs → Funnel → Deals activos → Categorías de marca → Oportunidades perdidas) enforced in HTML structure; "Fuente de leads" section excluded from per-talent view
- Loss reason always rendered as resolved Spanish label, never as integer ID — resolution happens in the service layer at query time
- 404 (not empty TalentDetail) returned for unknown talent_id to allow the frontend to handle selection errors cleanly

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Endpoint uses existing auth and DB.

## Human Checkpoint

**Task 4 (checkpoint:human-verify):** User verified Por talento tab in browser.
- Confirmed: talent selector populates correctly
- Confirmed: D-28 section order (KPIs → Funnel → Deals activos → Categorías de marca → Oportunidades perdidas)
- Confirmed: brand-category donut rendered by deal count
- Confirmed: Spanish razón-de-pérdida label pills display correctly
- **Result:** Approved

## Known Stubs

None - all sections wire to live data from the /dashboard/talents/{id} endpoint.

## Next Phase Readiness

- Per-talent endpoint and service layer are complete and stable; Phase 02 Plan 04 (Trello integration) can reference talent_detail() if talent-level Trello data is needed
- Phase 03 AI reports can call talent_detail(db, talent_id) directly as the primary data source for per-talent report sections
- All 65 tests green; no blockers

---
*Phase: 02-pipedrive-integration-core-dashboard*
*Completed: 2026-06-14*
