---
phase: 05-ai-generated-pdf-reports
plan: 04
subsystem: frontend-reports
tags: [reports, frontend, vanilla-js, css, xss-mitigation, dash-05]
dependency_graph:
  requires:
    - app/routers/reports.py::GET /reports/talents (from 05-02)
    - app/routers/reports.py::GET /reports/months (from 05-02)
    - app/routers/reports.py::POST /reports/generate (from 05-02)
    - app/routers/reports.py::GET /reports/ (from 05-03)
    - app/routers/reports.py::GET /reports/{id}/download (from 05-03)
    - frontend/js/dashboard.js::escHtml, showToast, setPage, apiFetch
  provides:
    - frontend/index.html::page-reportes (5th tab + full markup)
    - frontend/js/reports.js (loadReportTalents, loadReportMonths, generateReport, loadReportHistory, downloadReport)
    - frontend/js/dashboard.js::setPage reports branch
    - frontend/css/styles.css::.pdf-preview, .pdf-section, .pdf-block, .ai-badge (and 8 more classes)
    - tests/test_reports.py::TestReportesTabExists (smoke test green)
  affects:
    - frontend/index.html (5th tab added to tabbar)
    - frontend/js/dashboard.js (setPage extended with reports branch)
    - tests/test_reports.py (Wave-3 stub replaced, all 21 tests green)
tech_stack:
  added: []
  patterns:
    - escHtml() on all Claude narrative strings before innerHTML (T-xss / Pitfall 6)
    - apiFetch() for all /reports/* calls — never raw fetch() — handles 401 redirect
    - "Spinner via SVG + @keyframes spin injected at runtime (no external deps)"
    - Skeleton pulse via .pdf-skeleton + @keyframes skeletonPulse in styles.css
    - downloadReport() uses window.location.href — JWT is an httpOnly cookie, sent automatically
    - setPage reports branch pattern mirrors existing leads/talent/funnel branches
key_files:
  created:
    - frontend/js/reports.js
  modified:
    - frontend/index.html (5th tab + page-reportes + script tag)
    - frontend/css/styles.css (11 new .pdf-* + .ai-badge + skeleton classes)
    - frontend/js/dashboard.js (setPage reports branch)
    - tests/test_reports.py (test_reportes_tab_exists implemented)
decisions:
  - "D-72: downloadReport() uses window.location.href (not apiFetch blob) — JWT is httpOnly cookie sent automatically by browser on navigation; no need for manual fetch+blob pattern"
  - "D-73: @keyframes spin injected once at runtime via <style> element rather than adding to styles.css — avoids polluting global CSS with a JS-specific animation that only activates during generation"
  - "D-74: History rows use escHtml on both talent_name and formatted month label — defensive even though month is a YYYY-MM server-computed string"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-15"
  tasks_completed: 2
  files_created: 1
  files_modified: 4
---

# Phase 5 Plan 04: Reportes Tab UI Summary

**One-liner:** 5th Reportes tab with talent+month selects, AI generation spinner+skeleton+narrative preview card, history list, and PDF download, all wired to live /reports/* endpoints via apiFetch with full escHtml XSS mitigation; DASH-05 smoke gate green and 145 total tests passing.

## What Was Built

### Task 1: CSS classes + page-reportes markup + 5th tab + script tag

**`frontend/css/styles.css`** — 11 new classes added per UI-SPEC Component Inventory:

| Class | Role |
|-------|------|
| `.pdf-section` | `padding: 0 16px 24px` — wrapper around form + preview |
| `.pdf-preview` | Dark preview card (`var(--bg3)`, border, `var(--rL)`, overflow hidden) |
| `.pdf-preview-header` | Header with flex space-between (`var(--bg4)`, 16px padding, border-bottom) |
| `.pdf-preview-title` | 13px / font-weight 600 |
| `.pdf-preview-sub` | 11px / `var(--text3)` |
| `.pdf-body` | 16px padding — narrative content wrapper |
| `.pdf-block` | `margin-bottom: 16px` — per narrative section wrapper |
| `.pdf-block-title` | 10px uppercase Sora / `var(--text3)` / letter-spacing 0.8px |
| `.pdf-text` | 13px / `var(--text2)` / line-height 1.6 |
| `.pdf-text strong` | `var(--text)` / font-weight 600 |
| `.ai-badge` | Purple inline-flex badge (`var(--purpleD)` bg, `var(--purpleT)` text, 20px radius) |
| `.pdf-skeleton` | Skeleton loading line (`var(--bg5)`, 12px height, pulse animation) |

All values are 4px-grid multiples. Only font-weights 400 and 600 used.

**`frontend/index.html`** changes:
- Added `<div class="tab" onclick="setPage('reports', event)">Reportes</div>` to tabbar (5th tab)
- Added full `<div class="page" id="page-reportes">` block with:
  - Talent/month selects (`#report-talent`, `#report-month disabled`)
  - Empty state `#report-no-months` (`.alert.info` with UI-SPEC copy)
  - Preview card `#pdf-preview-card` (hidden initially, with `#pdf-preview-title`, `#pdf-preview-sub`, `.ai-badge`, `#pdf-body`)
  - `#btn-generate` (`.btn.primary`, disabled, `onclick="generateReport()"`)
  - `#btn-download` (`.btn`, disabled)
  - `.divider`
  - History section title + `#report-history` card
- Added `<script src="/js/reports.js"></script>` after `leads.js` (last in body)

All copy matches UI-SPEC Copywriting Contract exactly.

### Task 2: `frontend/js/reports.js` + setPage branch + DASH-05 test

**`frontend/js/reports.js`** — 362 lines, 5 public functions:

| Function | Trigger | API | DOM target |
|----------|---------|-----|------------|
| `loadReportTalents()` | `setPage('reports')` | GET /reports/talents | #report-talent |
| `loadReportMonths(talentId)` | onChange #report-talent | GET /reports/months?talent_id= | #report-month, #report-no-months, #btn-generate |
| `generateReport()` | click #btn-generate | POST /reports/generate | #pdf-preview-card, #pdf-body, #btn-download |
| `loadReportHistory()` | setPage + after generation | GET /reports/ | #report-history |
| `downloadReport(reportId)` | click fila / btn-download | — | window.location.href redirect |

XSS mitigation (T-xss): all three narrative fields (`resumen_ejecutivo`, `deals_destacados`, `recomendacion`) wrapped in `escHtml()` before innerHTML. History row `talent_name` and `monthLabel` also escaped. No raw Claude text touches the DOM.

State machine per UI-SPEC:
- **Estado 1** (tab load): talent dropdown populated, history loaded, month disabled
- **Estado 2** (talent selected): months populated, btn-generate enabled; or empty state shown
- **Estado 3** (generating): btn-generate disabled with SVG spinner + "Generando...", skeleton in pdf-body
- **Estado 4** (success): narrative rendered, btn-download enabled, history reloaded, success toast
- **Estado 5** (download): window.location.href to /reports/{id}/download
- **Estado 6** (error): btn-generate re-enabled, preview hidden, error toast

**`frontend/js/dashboard.js`** — setPage extended with reports branch calling `loadReportTalents()` and `loadReportHistory()`.

**`tests/test_reports.py`** — `test_reportes_tab_exists` implemented (replaces Wave-3 stub): asserts `page-reportes` in index.html, `setPage('reports'` in index.html, and `frontend/js/reports.js` exists on disk. Test passes.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 5e778ee | feat(05-04): add Reportes tab markup, CSS classes, and 5th tab in tabbar |
| Task 2 | f369733 | feat(05-04): implement reports.js, setPage reports branch, DASH-05 smoke test |

## Deviations from Plan

None — plan executed exactly as written.

Minor implementation notes (not deviations):
- The `@keyframes spin` for the generating spinner is injected once at runtime via a `<style>` element (avoiding pollution of `styles.css` with a JS-specific animation).
- `downloadReport()` uses `window.location.href` (not `apiFetch` blob) because the JWT is carried as an httpOnly cookie, sent automatically by the browser on navigation — matching the plan's recommended approach.

## Known Stubs

None. All 5 module-contract functions are fully implemented and wired to live endpoints.

## Threat Surface Scan

| T-ID | Disposition | Implementation |
|------|-------------|----------------|
| T-xss | mitigated | `escHtml()` applied to all Claude narrative fields + history talent names before innerHTML; grep gate confirmed in Task 2 verify |
| T-unauth-ui | mitigated | All calls use `apiFetch` which carries JWT cookie and redirects to /login.html on 401 |
| T-csrf-gen | accepted | Same-origin Vanilla JS app; POST /reports/generate is same-origin only; generation writes to local SQLite+disk only |

No new trust boundaries introduced beyond the plan's STRIDE register.

## Self-Check: PASSED

- [x] `frontend/index.html` contains `page-reportes`, `setPage('reports'`, `report-talent`, `report-month`, `btn-generate`, `btn-download`, `report-history`, `/js/reports.js`
- [x] `frontend/css/styles.css` contains `.pdf-preview`, `.pdf-preview-header`, `.pdf-preview-title`, `.pdf-preview-sub`, `.pdf-body`, `.pdf-block`, `.pdf-block-title`, `.pdf-text`, `.ai-badge`
- [x] `frontend/js/reports.js` exists (362 lines), defines loadReportTalents, loadReportMonths, generateReport, loadReportHistory, downloadReport
- [x] `escHtml(` used in reports.js; `function escHtml` NOT redefined in reports.js
- [x] `apiFetch("/reports` present in reports.js; no raw `fetch(` for API calls
- [x] `name === "reports"` branch present in dashboard.js setPage
- [x] `test_reportes_tab_exists` PASSED
- [x] Full test suite: 145 passed, 0 failed
- [x] Commits 5e778ee and f369733 exist in git log
