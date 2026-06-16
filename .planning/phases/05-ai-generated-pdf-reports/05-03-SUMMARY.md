---
phase: 05-ai-generated-pdf-reports
plan: 03
subsystem: reports
tags: [reports, router, download, history, fileresponse, auth, tests]
dependency_graph:
  requires:
    - app/services/reports.py::list_reports (from 05-02)
    - app/models.py::Report, Talent (from 05-01)
    - app/schemas/reports.py::ReportHistoryItem (from 05-01)
    - app/routers/reports.py (from 05-02, extended here)
    - tests/conftest.py::mock_anthropic, mock_weasyprint (from 05-01)
  provides:
    - app/routers/reports.py::GET /reports/ (history list, newest-first)
    - app/routers/reports.py::GET /reports/{id}/download (FileResponse, PDF attachment)
    - tests/test_reports.py::TestListReports (3 tests, all green)
    - tests/test_reports.py::TestDownloadReport (4 tests, all green)
  affects:
    - tests/test_reports.py (Wave 2 stubs replaced by real implementations)
tech_stack:
  added: []
  patterns:
    - FileResponse with media_type="application/pdf" and Content-Disposition header
    - os.path.exists guard before FileResponse — returns 404 instead of 500 on stale DB row (T-stale-path)
    - Router-level dependencies=[Depends(get_current_user)] covers GET / and GET /{id}/download without per-endpoint auth
    - Static path /reports/ defined before parameterized /reports/{id}/download to ensure correct routing order
    - Test inserts stale Report row with nonexistent file_path to verify T-stale-path 404 defense
key_files:
  created: []
  modified:
    - app/routers/reports.py (added GET /reports/ and GET /reports/{id}/download)
    - tests/test_reports.py (Wave 2 stubs replaced: TestListReports × 3, TestDownloadReport × 4)
decisions:
  - "D-69: GET /reports/ placed before GET /{report_id}/download so the static path is matched first (FastAPI route ordering)"
  - "D-70: filename uses talent_name.replace(' ', '-') for readability, not talent.id slug — the ID slug is only needed for filesystem paths (T-path-traversal), not for Content-Disposition filenames"
  - "D-71: test_download_missing_file inserts Report row directly via db_session with nonexistent path, avoiding a generate+delete cycle"
metrics:
  duration: "~12 minutes"
  completed: "2026-06-15"
  tasks_completed: 2
  files_created: 0
  files_modified: 2
---

# Phase 5 Plan 03: History List and Download Endpoints Summary

**One-liner:** GET /reports/ history list (newest-first) and GET /reports/{id}/download (FileResponse PDF attachment) added to the reports router, both auth-protected at router level, with 404 guards for missing report row and stale file path; 7 new Wave-2 tests all green.

## What Was Built

### Task 1: History list + download endpoints in `app/routers/reports.py`

Added two new imports (`os`, `FileResponse`) and the `Report` model, then appended two endpoints after the existing `generate_report` endpoint:

**GET /reports/** (`list_reports`):
- `response_model=list[ReportHistoryItem]`
- Calls `reports_service.list_reports(db)` and returns `[ReportHistoryItem(**row) for row in rows]`
- Inherits router-level `dependencies=[Depends(get_current_user)]` — no per-endpoint auth needed

**GET /reports/{report_id}/download** (`download_report`):
- Fetches `Report` row via `db.get(Report, report_id)` → 404 if absent
- Checks `os.path.exists(report.file_path)` → 404 if file missing (T-stale-path defense)
- Resolves `Talent.name`, builds filename `reporte-{talent_name}-{month}.pdf` with spaces→hyphens
- Returns `FileResponse(path=..., media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=..."})`

Route ordering: `GET /reports/` (static) defined before `GET /reports/{report_id}/download` (parameterized) as required by FastAPI routing semantics.

### Task 2: Wave-2 tests in `tests/test_reports.py`

Replaced all 6 Wave-1 stub bodies in `TestListReports` and `TestDownloadReport` with real implementations. Added a 7th test (`test_download_missing_file`) which was specified in the plan but had no corresponding stub:

| Test | Class | Assert |
|------|-------|--------|
| `test_list_reports_requires_auth` | `TestListReports` | GET /reports/ without auth → 401 |
| `test_list_reports_returns_empty_list` | `TestListReports` | authenticated, empty DB → 200 [] |
| `test_list_reports_returns_generated_reports` | `TestListReports` | generate → list → all ReportHistoryItem fields present, newest-first |
| `test_download_requires_auth` | `TestDownloadReport` | GET /reports/1/download without auth → 401 |
| `test_download_returns_pdf` | `TestDownloadReport` | generate → download → 200, application/pdf, Content-Disposition: attachment |
| `test_download_404_for_missing_report` | `TestDownloadReport` | nonexistent report_id → 404 |
| `test_download_missing_file` | `TestDownloadReport` | stale Report row with /nonexistent/path.pdf → 404 |

All 7 tests pass. All 13 Wave-1 tests continue to pass (total 20 green, 1 Wave-3 stub deselected).

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | df5f846 | feat(05-03): add GET /reports/ history list + GET /reports/{id}/download endpoints |
| Task 2 | 6a97641 | feat(05-03): implement list_reports + download tests (Wave 2 — 05-03) |

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

The plan specified tests with names `test_list_reports`, `test_download_report`, `test_download_requires_auth`, and `test_download_missing_file`. The existing stub class had `test_download_returns_pdf` instead of `test_download_report`. The implementation used the stub's name (`test_download_returns_pdf`) to avoid renaming a class method that was already part of the public test surface, and added `test_download_missing_file` as the 4th test as specified. This is not a deviation — names are functionally equivalent.

## Known Stubs

One Wave-3 stub remains in `tests/test_reports.py` (intentional — implemented in 05-04):

| Stub | Class | Wave |
|------|-------|------|
| `test_reportes_tab_exists` | `TestReportesTabExists` | 05-04 |

## Threat Surface Scan

No new trust boundaries beyond what was planned. Both endpoints are covered by the existing STRIDE register:

| T-ID | Disposition | Implementation |
|------|-------------|----------------|
| T-unauth-dl | mitigated | Router-level `dependencies=[Depends(get_current_user)]` covers both new endpoints; `test_list_reports_requires_auth` + `test_download_requires_auth` verify 401 |
| T-stale-path | mitigated | `os.path.exists(report.file_path)` → 404 before FileResponse; `test_download_missing_file` verifies behavior |
| T-idor-download | accepted | All authenticated users share one access level (RBAC deferred per FUT-03 / Out of Scope) |

## Self-Check: PASSED

- [x] `app/routers/reports.py` — contains `FileResponse`, `Content-Disposition`, `os.path.exists`, `/reports/` route, `/reports/{report_id}/download` route
- [x] Routes `/reports/` and `/reports/{report_id}/download` confirmed registered via `app.routes` check
- [x] `tests/test_reports.py` — 20 tests pass (7 Wave-2 new + 13 Wave-1 retained); 1 Wave-3 stub deselected
- [x] Commits df5f846 and 6a97641 exist in `git log`
- [x] No STATE.md or ROADMAP.md modifications made (orchestrator owns those writes)
