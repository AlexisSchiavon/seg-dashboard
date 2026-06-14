---
phase: 03-google-sheets-leads-integration
plan: 02
subsystem: leads-ui
tags: [leads, frontend, api, tdd, xss-mitigation]
dependency_graph:
  requires: ["03-01"]
  provides: ["DASH-04", "SHEET-02-classification-surface"]
  affects: ["frontend/index.html", "frontend/js/dashboard.js", "frontend/js/leads.js", "app/services/leads.py", "app/routers/leads.py"]
tech_stack:
  added: []
  patterns:
    - "leads_list service function with joinedload for talent_name resolution"
    - "talent_id 404 guard at router layer (same pattern as dashboard.py)"
    - "D-36 score pills: 0-40 red, 41-70 amber, 71-100 green via CSS vars"
    - "escHtml on all Sheet-sourced strings before innerHTML (CR-02 T-03B-01)"
    - "status param shadowing fastapi.status fixed via aliased import http_status"
    - "leads.js loaded after dashboard.js — reuses escHtml/apiFetch/showToast"
key_files:
  created:
    - frontend/js/leads.js
  modified:
    - app/services/leads.py
    - app/routers/leads.py
    - frontend/index.html
    - frontend/js/dashboard.js
    - tests/test_leads.py
decisions:
  - "Named fastapi.status import as http_status to avoid shadowing by query param named 'status'"
  - "GET /leads uses empty-string path ('') not '/' to avoid FastAPI redirect ambiguity with router prefix /leads"
  - "scorePillColor returns CSS var strings rather than class names — avoids adding new CSS"
  - "loadLeads wired to filter-change events at DOMContentLoaded; tab activation calls both loadLeadsSummary and loadLeads"
metrics:
  duration: "~20 min"
  completed: "2026-06-14"
  tasks_completed: 2
  files_changed: 5
---

# Phase 03 Plan 02: Leads Tab UI Vertical Slice Summary

**One-liner:** GET /leads endpoint with talent_name/status_display resolution, filterable by talent/status/fuente, paired with a full Leads tab rendering per-talent bars and D-36 score pills via escHtml-protected innerHTML.

## Tasks Completed

| # | Name | Commit | Key Files |
|---|------|--------|-----------|
| 1 (TDD RED) | Failing tests for leads_list + GET /leads | 838a95c | tests/test_leads.py |
| 1 (TDD GREEN) | leads_list service + GET /leads endpoint | f569dea | app/services/leads.py, app/routers/leads.py |
| 2 | Leads tab HTML + leads.js + dashboard.js wiring | 3b82652 | frontend/index.html, frontend/js/leads.js, frontend/js/dashboard.js |

## What Was Built

### Task 1 — leads_list service + GET /leads endpoint

Added `leads_list(db, talent_id, status, fuente)` to `app/services/leads.py`:
- SQLAlchemy `joinedload(Lead.talent)` to resolve `talent_name` in one query
- `STATUS_DISPLAY.get(status_filtrado, status_filtrado)` for display label with unmapped fallback
- Ordered by `fecha_recepcion DESC nulls last`, then `sheet_row_id DESC`
- Parameterized filters only — no raw SQL (T-03B-03)

Added `GET /leads` to `app/routers/leads.py`:
- `response_model=list[LeadRow]`
- `talent_id: int | None` coerced by FastAPI (422 on non-int, 404 on nonexistent)
- Auth-protected via router-level `dependencies=[Depends(get_current_user)]` (T-03B-02)
- Uses aliased `from fastapi import status as http_status` to avoid shadowing by `status` query param

### Task 2 — Leads tab HTML + leads.js + dashboard.js

**frontend/index.html:**
- 4th tab: `<div class="tab" onclick="setPage('leads', event)">Leads</div>`
- `#page-leads` section: `#leads-kpi-grid`, `#leads-by-talent`, filter selects, `#leads-list`
- `<script src="/js/leads.js">` loaded after dashboard.js

**frontend/js/leads.js (new file):**
- `scorePillColor(score)` — D-36 color mapping returning CSS var pair strings
- `statusPillStyle(statusDisplay)` — Aprobado/Bloqueado/En revision color mapping
- `loadLeadsSummary()` — fetches `/leads/summary`, renders KPI tiles + per-talent source-row bars; calls `populateTalentFilter()`
- `loadLeads()` — builds query string from dropdowns, fetches `/leads`, renders deal-row leads list
- ALL Sheet-sourced strings (remitente_nombre, remitente_email, asunto, talent_name, status_display) pass through `escHtml` — T-03B-01 CR-02 mitigation (10 usages)
- Does NOT redefine `apiFetch`, `escHtml`, `showToast` (loaded from auth.js/dashboard.js)

**frontend/js/dashboard.js:**
- Added `leads` branch to `setPage()` calling `loadLeadsSummary()` then `loadLeads()`

## TDD Gate Compliance

- RED gate: `test(03-02)` commit 838a95c — 11 failing tests added before implementation
- GREEN gate: `feat(03-02)` commit f569dea — all 11 new tests passing + 97 prior = 108 total
- No REFACTOR step needed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] fastapi.status shadowed by query param named 'status'**
- **Found during:** Task 1 implementation
- **Issue:** `def list_leads(status: str | None = None, ...)` with `from fastapi import status` causes the parameter to shadow the module-level import, making `status.HTTP_404_NOT_FOUND` raise AttributeError at runtime
- **Fix:** Changed to `from fastapi import status as http_status` and used `http_status.HTTP_404_NOT_FOUND`
- **Files modified:** app/routers/leads.py
- **Commit:** f569dea (included in same feat commit)

## Test Coverage

108 tests passing (11 new in this plan, 97 from prior plans):

New tests:
- `test_leads_list_all_returns_all_with_talent_name` — talent_name resolved from join
- `test_leads_list_all_includes_status_display` — STATUS_DISPLAY mapping all 3 values
- `test_leads_list_filter_talent` — talent_id filter
- `test_leads_list_filter_status` — status_filtrado filter
- `test_leads_list_filter_fuente` — fuente filter
- `test_leads_list_unmapped_status_falls_back_to_raw` — STATUS_DISPLAY fallback
- `test_leads_endpoint_auth` — 200 with valid JWT
- `test_leads_endpoint_unauth` — 401 without JWT
- `test_leads_endpoint_filter_talent_404` — 404 on nonexistent talent_id
- `test_leads_endpoint_filter_talent_valid` — filters results correctly
- `test_leads_endpoint_has_required_fields` — all LeadRow fields present in response

## Known Stubs

None. All data is wired to live API endpoints (/leads, /leads/summary). Filter dropdowns populate dynamically from /leads/summary data at tab activation.

## Self-Check: PASSED

Files confirmed present:
- FOUND: frontend/js/leads.js
- FOUND: app/services/leads.py
- FOUND: app/routers/leads.py
- FOUND: frontend/index.html
- FOUND: frontend/js/dashboard.js

Commits confirmed in git log:
- 838a95c: test(03-02): add failing tests for leads_list service and GET /leads endpoint
- f569dea: feat(03-02): leads_list service + filterable GET /leads endpoint
- 3b82652: feat(03-02): Leads tab HTML, leads.js render, dashboard.js setPage wiring
