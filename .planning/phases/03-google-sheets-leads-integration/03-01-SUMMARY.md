---
phase: 03-google-sheets-leads-integration
plan: "01"
subsystem: leads-sync
tags: [google-sheets, gspread, sqlite, sync, leads, classification]
dependency_graph:
  requires: [02-03]
  provides: [leads-table, sheets-integration, leads-service, sync-sheets-job]
  affects: [03-02, 03-03]
tech_stack:
  added:
    - gspread>=6.1,<7.0
    - google-auth>=2.40,<3.0
  patterns:
    - SheetLeadRow Pydantic model with field_validators (mode="before") for Sheet-sourced coercion
    - sync_sheets source-isolated concurrency guard (SyncLog.source == "sheets")
    - talent_map dict pre-built once per sync to avoid N+1 queries
    - staticmethod lambda in monkeypatch fixture to prevent implicit self-injection
key_files:
  created:
    - app/integrations/sheets.py
    - app/services/leads.py
    - app/routers/leads.py
    - app/schemas/leads.py
    - alembic/versions/d48d69b17ea6_add_leads_table.py
    - tests/test_leads.py
  modified:
    - app/models.py
    - app/sync/jobs.py
    - app/sync/scheduler.py
    - app/routers/sync.py
    - app/main.py
    - tests/conftest.py
    - pyproject.toml
decisions:
  - "Natural key is sheet_row_id (row number), not ID_Lead — ID_Lead is empty for all 730 live rows (A1: append-only assumption)"
  - "Concurrency guard filters by SyncLog.source == 'sheets' to prevent cross-source collision (Pitfall 6)"
  - "talent_map pre-built once per sync (dict[name->id]) to avoid N+1 DB queries per row"
  - "QUALIFIED_STATUS uses exact emoji literal string — verified against 730 live rows, average score 75.4"
  - "staticmethod wrapper required for lambda in type() mock to prevent Python injecting self"
  - "gspread and google-auth added to pyproject.toml (pre-approved T-03-SC; were missing from dependencies)"
metrics:
  duration_minutes: 8
  completed_date: "2026-06-14"
  tasks_completed: 3
  files_created: 6
  files_modified: 7
  tests_added: 32
  total_tests: 97
---

# Phase 03 Plan 01: Google Sheets Leads Sync Vertical Slice Summary

**One-liner:** Read-only gspread integration syncing Sheets leads to SQLite via idempotent upsert by sheet_row_id, with emoji-exact QUALIFIED_STATUS classification and source-isolated concurrency guard.

## What Was Built

Built the complete Google Sheets to SQLite leads sync pipeline:

1. **Lead model + migration** (`app/models.py`, `alembic/versions/d48d69b17ea6`): `Lead` SQLAlchemy model with `sheet_row_id` as the unique natural key (ID_Lead is empty in all 730 live rows). Migration `d48d69b17ea6` applied (down_revision=`c35f623eaa21`), creating the leads table with 3 indexes (sheet_row_id unique, talent_id, status_filtrado).

2. **Read-only gspread integration** (`app/integrations/sheets.py`): `_client()` factory using `google.oauth2.service_account.Credentials` + `gspread.authorize()`. `SheetLeadRow` Pydantic model with `field_validators` coercing Sheet strings to Python types before DB write (empty to None, "TRUE" to True, "85.0" to 85). `get_leads_rows()` pads short rows to header length (Pitfall 2). Module docstring states the READ-ONLY constraint and security note. Zero write methods in the module.

3. **Leads classification service** (`app/services/leads.py`): `QUALIFIED_STATUS = "✅ Aprobado - Respuesta enviada"` (emoji literal, exact match), `STATUS_DISPLAY` map, `resolve_talent_id()` (exact match, empty/whitespace to None), `leads_summary()` (total + calificados counts), `leads_by_talent()` (outerjoin + Sin-talento bucket when talent_id IS NULL count > 0).

4. **sync_sheets job** (`app/sync/jobs.py`): `_parse_fecha()` helper parsing ISO dates with Z-suffix. `sync_sheets()` with source='sheets' concurrency guard (Pitfall 6: filtered by both source AND status to avoid cross-source collision), talent_map pre-built once to avoid N+1, idempotent upsert by sheet_row_id, `str(exc)`-only error handling (T-03-01 threat mitigation).

5. **Scheduler and manual sync wiring**: `app/sync/scheduler.py` replaced `_run_pipedrive_sync` with `_run_all_syncs()` (Pipedrive then Sheets, job id=`sync_all`). `app/routers/sync.py` extended `_run_sync_in_background` to call both syncs.

6. **Leads API router** (`app/routers/leads.py`): `GET /leads/summary` with router-level `Depends(get_current_user)` (T-03-03). Returns `LeadsSummary(leads_totales, calificados, por_talento)`. Registered in `app/main.py` before the static mount.

7. **Test scaffold** (32 tests, all green): `SheetLeadRow` validator tests, padding tests, `resolve_talent_id` tests, `leads_summary`/`leads_by_talent` tests, `sync_sheets` idempotency/source-isolation/concurrency tests, endpoint auth tests.

## Test Results

```
97 passed in 2.05s (65 pre-existing + 32 new)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] gspread and google-auth missing from pyproject.toml**
- **Found during:** Task 1 — `ModuleNotFoundError: No module named 'gspread'`
- **Issue:** Both packages were documented as required in STACK.md and pre-approved in T-03-SC of the threat model, but were not in `pyproject.toml` dependencies.
- **Fix:** Added `gspread>=6.1,<7.0` and `google-auth>=2.40,<3.0` to pyproject.toml; ran `uv sync`.
- **Files modified:** `pyproject.toml`, `uv.lock`
- **Commit:** 3024460

**2. [Rule 1 - Bug] mock_sheets_rows fixture lambda receives unexpected 'self'**
- **Found during:** Task 2 — sync_sheets returning status='error' with message "takes 0 positional arguments but 1 was given"
- **Issue:** `type("_MockSheets", (), {"get_leads_rows": lambda: sample})()` — when Python looks up `get_leads_rows` on an instance, it treats the plain lambda as an unbound method and injects `self` as the first argument. The 03-PATTERNS.md pattern had this same bug.
- **Fix:** Wrapped the lambda with `staticmethod()` so Python skips the descriptor protocol: `staticmethod(lambda: sample)`.
- **Files modified:** `tests/conftest.py`
- **Commit:** 5d6a5be

## Known Stubs

None. All data flows through the actual sync pipeline. The `GET /leads/summary` endpoint returns real database counts (0 when no sync has been run). No hardcoded values or placeholder text.

## Threat Surface Scan

All surfaces were covered by the plan's `<threat_model>`:

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-03-01 | sync_sheets catches Exception and persists only `str(exc)` — gspread objects never logged |
| T-03-02 | sheets.py contains only `get_all_values()` — zero write methods (verified by code inspection) |
| T-03-03 | `app/routers/leads.py` has router-level `dependencies=[Depends(get_current_user)]` — 401 without JWT |
| T-03-04 | `SheetLeadRow` field_validators coerce all Sheet values before DB write — bad data to None/False |
| T-03-SC | gspread/google-auth installed from canonical PyPI (pre-approved in STACK.md audit) |

No new security surfaces beyond what the plan specified.

## Self-Check: PASSED

Files exist:
- `app/integrations/sheets.py` — FOUND
- `app/services/leads.py` — FOUND
- `app/routers/leads.py` — FOUND
- `app/schemas/leads.py` — FOUND
- `alembic/versions/d48d69b17ea6_add_leads_table.py` — FOUND
- `tests/test_leads.py` — FOUND

Commits exist:
- d578ca1 (Task 0: Lead model, migration, schemas, test scaffold)
- 3024460 (Task 1: gspread integration, leads service)
- 5d6a5be (Task 2: sync_sheets, scheduler, router, main)
