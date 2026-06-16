---
phase: 05-ai-generated-pdf-reports
plan: 02
subsystem: reports
tags: [reports, service, router, jinja2, weasyprint, anthropic, tdd, pdf]
dependency_graph:
  requires:
    - app/models.py::Report (from 05-01)
    - app/schemas/reports.py (from 05-01)
    - tests/conftest.py::mock_anthropic, mock_weasyprint (from 05-01)
    - app/services/kpis.py::talent_detail
    - app/services/funnel.py::talent_funnel
    - app/services/leads.py::leads_summary, leads_by_talent
  provides:
    - app/services/reports.py (available_months, generate_report, list_reports)
    - app/routers/reports.py (GET /reports/talents, GET /reports/months, POST /reports/generate)
    - templates/reports/template.html (Jinja2 PDF template, light theme)
    - app/main.py::reports.router (registered before StaticFiles)
  affects:
    - tests/test_reports.py (Wave 1 tests now GREEN: 13 passing)
    - .gitignore (/reports/ root-anchored fix)
tech_stack:
  added: []
  patterns:
    - TDD RED→GREEN cycle: tests committed first, service implementation second
    - Lazy WeasyPrint import inside _render_pdf() — mock-safe for macOS/CI (no Pango/Cairo)
    - HTML module-level sentinel (HTML = None) patched by mock_weasyprint fixture
    - Atomic PDF write: HTML writes to .tmp then os.replace() to final path (Pitfall 4)
    - base_url="." literal in _render_pdf — never user-controlled (T-ssrf defense)
    - str(talent.id) slug for file paths — numeric only, T-path-traversal defense
    - Router-level dependencies=[Depends(get_current_user)] protects all 3 endpoints
    - generate_report endpoint is sync def (not async def) — WeasyPrint blocking I/O
    - ValueError disambiguation in router: "non-JSON" → 502, talent missing → 404
key_files:
  created:
    - app/services/reports.py
    - app/routers/reports.py
    - templates/reports/template.html
  modified:
    - tests/test_reports.py (Wave 0 stubs → Wave 1 implemented tests, stubs preserved for 05-03/04)
    - app/main.py (reports.router added after leads.router, before StaticFiles)
    - .gitignore (/reports/ root-anchored, was reports/ — bug fix)
decisions:
  - "D-65: lazy import of weasyprint.HTML inside _render_pdf() — module-level import fails on macOS without Pango/Cairo; HTML = None sentinel allows monkeypatch to work before actual use"
  - "D-66: _build_payload returns only JSON-serializable scalars — kpis extracted from talent_detail kpis list by label key ('Pipeline', 'Cerrados', 'Comisión')"
  - "D-67: ValueError disambiguation in router — checks for 'non-JSON' substring to route to 502 vs default 404 for talent not found"
  - "D-68: .gitignore root-anchor fix — changed 'reports/' to '/reports/' so templates/reports/ is not ignored"
metrics:
  duration: "~35 minutes"
  completed: "2026-06-15"
  tasks_completed: 3
  files_created: 3
  files_modified: 3
---

# Phase 5 Plan 02: Core Generation Vertical Slice — Service, Template, Router Summary

**One-liner:** Full reports pipeline: Python-computed payload → Claude narrative call (mocked) → Jinja2+WeasyPrint PDF render (mocked) → atomic disk write → Report upsert → 3 REST endpoints auth-protected, 13 Wave-1 tests green.

## What Was Built

### Task 1 (TDD): `app/services/reports.py`

Service module implementing the full generation orchestration:

- `available_months(db, talent_id)`: Queries `Deal.add_time`, extracts `[:7]` slices, validates against `r'\d{4}-\d{2}'`, returns sorted descending unique set. Returns `[]` for unknown talent.
- `_build_payload(db, talent, month)`: Assembles 100% Python-computed dict from `kpis_service.talent_detail()`, `funnel_service.talent_funnel()`, `leads_service.leads_summary()`, `leads_service.leads_by_talent()`, and a direct query for top 3 open deals. Guaranteed JSON-serializable — no ORM instances.
- `_call_claude(payload)`: Calls `claude-sonnet-4-6` with `max_tokens=1500` and a SYSTEM_PROMPT instructing Claude to use only the provided JSON numbers. Strips markdown fences, `json.loads()`, raises `ValueError("Claude returned non-JSON")` on parse failure.
- `_slug(talent)`: Returns `str(talent.id)` — purely numeric, T-path-traversal defense.
- `_render_pdf(html_str, output_path)`: Lazy-imports WeasyPrint HTML inside the function (mock-safe); writes to `.tmp` then `os.replace()` (atomic write, Pitfall 4); `base_url="."` literal (T-ssrf defense).
- `generate_report(db, talent_id, month)`: Orchestrator — ValueError if talent missing; calls `_build_payload → _call_claude → _render_pdf`; upserts Report row.
- `list_reports(db)`: All Report rows ordered by `generated_at` desc with `talent_name` resolved.

**TDD commits:** `test(05-02)` RED commit → `feat(05-02)` GREEN commit (separate).

### Task 2: `templates/reports/template.html`

Self-contained light-theme Jinja2 HTML with inline `<style>`:

- Font: `'Helvetica Neue', Arial, sans-serif` (system stack — no Google Fonts URL)
- Light theme: `#ffffff` background, `#1a1a1a` primary text, `#e8520a` accent, `#6b54d6` purple badge
- 5 sections in order: (1) cover with talent name 28px/700/`#e8520a`, month, "✦ Generado con Claude AI" badge; (2) Resumen ejecutivo; (3) Deals destacados; (4) Recomendación; (5) KPI appendix table
- autoescape=True in Jinja2 Environment — narrative prose is HTML-escaped
- Jinja2 variables: `{{ talent_name }}`, `{{ month }}`, `{{ narrative.resumen_ejecutivo }}`, `{{ narrative.deals_destacados }}`, `{{ narrative.recomendacion }}`, `{{ data.kpis.* }}`
- Funnel stages table and top 3 deals table (conditional with `{% if %}`)

### Task 3: `app/routers/reports.py` + `app/main.py`

Three endpoints under `/reports`, all auth-protected at router level:

| Endpoint | Type | Notes |
|----------|------|-------|
| `GET /reports/talents` | `def` | Active talents `[{id, name}]`, alphabetical |
| `GET /reports/months` | `def` | `available_months(db, talent_id)` |
| `POST /reports/generate` | `def` (NOT async) | WeasyPrint blocking; 404 on talent missing, 502 on Claude non-JSON |

`app/main.py`: `from app.routers import reports` added; `app.include_router(reports.router)` after `leads.router`, before `StaticFiles` mount.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 RED | 8e94cd1 | test(05-02): add failing tests for available_months, payload, pdf write, generate endpoint |
| Task 1 GREEN | e5acbb6 | feat(05-02): implement reports service — available_months, payload, Claude call, PDF render, upsert |
| Task 2 | 8b43b4b | feat(05-02): create light-theme Jinja2 PDF template with SEG branding |
| Task 3 | ab65ecf | feat(05-02): add reports router and wire into main.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `from weasyprint import HTML` fails at import time on macOS (no Pango/Cairo)**
- **Found during:** Task 1 GREEN phase (first test run after creating service)
- **Issue:** Module-level `from weasyprint import HTML` raised `OSError: cannot load library 'libgobject-2.0-0'` on macOS in the test environment. This failed the import before `mock_weasyprint` fixture could patch anything.
- **Fix:** Changed to lazy import inside `_render_pdf()` only. Added `HTML = None` as a module-level sentinel so monkeypatch can replace it with `mock_weasyprint`. In production (Docker with Pango/Cairo installed), the lazy import succeeds on first real PDF render.
- **Files modified:** `app/services/reports.py`
- **Commit:** e5acbb6

**2. [Rule 1 - Bug] `.gitignore` `reports/` pattern also ignored `templates/reports/`**
- **Found during:** Task 2 commit
- **Issue:** The pattern `reports/` in `.gitignore` matches any directory named `reports/` at any depth, including `templates/reports/`. `git add templates/reports/template.html` failed with "ignored by gitignore".
- **Fix:** Changed `reports/` to `/reports/` (root-anchored) so only the `/reports/` PDF output directory at project root is excluded. `templates/reports/` is now tracked by git.
- **Files modified:** `.gitignore`
- **Commit:** 8b43b4b

## Known Stubs

Wave 2/3 stubs remain in `tests/test_reports.py` (intentional — implemented in 05-03 and 05-04):

| Stub | Class | Wave |
|------|-------|------|
| `test_list_reports_*` (3 tests) | `TestListReports` | 05-03 |
| `test_download_*` (3 tests) | `TestDownloadReport` | 05-03 |
| `test_reportes_tab_exists` | `TestReportesTabExists` | 05-04 |

## Threat Surface Scan

No new trust boundaries introduced beyond what was planned in the STRIDE register:

| T-ID | Disposition | Implementation |
|------|-------------|----------------|
| T-path-traversal | mitigated | `_slug()` returns `str(talent.id)` — numeric only, confirmed by test `test_pdf_path_uses_talent_id_not_name` |
| T-ssrf | mitigated | `base_url="."` literal in `_render_pdf()` — grep confirms no user variable |
| T-prompt-injection | accepted | Deal data embedded as JSON in user message; SYSTEM_PROMPT instructs data-only treatment |
| T-claude-numbers | mitigated | All PDF appendix figures from Python; Claude output only used for 3 prose sections |

## TDD Gate Compliance

- [x] RED commit exists: `8e94cd1` (`test(05-02):`)
- [x] GREEN commit exists: `e5acbb6` (`feat(05-02):`)
- [x] All 13 Wave-1 tests pass in GREEN state

## Self-Check: PASSED

- [x] `app/services/reports.py` exists — 324 lines, 7 functions: `available_months`, `_build_payload`, `_call_claude`, `_slug`, `_render_pdf`, `generate_report`, `list_reports`
- [x] `app/routers/reports.py` exists — contains `dependencies=[Depends(get_current_user)]`, `def generate_report` (not async)
- [x] `templates/reports/template.html` exists — contains `narrative.resumen_ejecutivo`, `narrative.deals_destacados`, `narrative.recomendacion`, `#e8520a`, `Helvetica Neue`
- [x] `app/main.py` contains `reports.router` — registered before StaticFiles mount
- [x] `tests/test_reports.py` — 13 Wave-1 tests PASS, 7 Wave-2/3 stubs FAIL as expected
- [x] Commits 8e94cd1, e5acbb6, 8b43b4b, ab65ecf exist in git log
- [x] Routes `/reports/talents`, `/reports/months`, `/reports/generate` confirmed registered
- [x] SYNC_DEF_OK: `generate_report` endpoint is `def` not `async def`
