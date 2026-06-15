---
phase: 03-google-sheets-leads-integration
verified: 2026-06-14T18:15:00Z
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open dashboard, log in, click the Leads tab. Confirm the per-talent bars render with '{total} leads · {calificados} calificados' text, and the leads list shows rows with colored score pills (red/amber/green per score range)."
    expected: "Bars and leads list populate from the /leads/summary and /leads API. Score pills are color-coded: 0-40 red, 41-70 amber, 71-100 green, null neutral grey."
    why_human: "Browser rendering of CSS var() color pairs and dynamic innerHTML cannot be verified programmatically."
  - test: "On the Leads tab, change the Talent dropdown to a specific talent. Confirm the list filters to only that talent's leads. Change Status dropdown to 'Aprobado'. Confirm only approved leads show."
    expected: "Each filter change triggers a re-fetch of /leads with the corresponding query param and the list re-renders."
    why_human: "DOM event wiring and visual filter behavior require a browser."
  - test: "On the Resumen tab, confirm 'Leads totales' and 'Calificados' tiles show real integer counts (not '--' and not 'undefined') after page load."
    expected: "Tiles display the same counts as seen on the Leads tab KPI grid, populated by renderLeadsOverviewKpis via loadSummary on DOMContentLoaded."
    why_human: "Tile content is set via textContent at runtime; requires visual inspection."
  - test: "Trigger 'Sincronizar ahora', then check Leads tab: confirm rows appear (or counts increase) after the sync completes."
    expected: "sync_sheets is called as part of _run_sync_in_background; leads table is populated/updated, and Leads tab reflects new data after tab reload."
    why_human: "End-to-end sync requires a live Google Sheets credential and network access."
---

# Phase 03: Google Sheets Leads Integration Verification Report

**Phase Goal:** Integrate Google Sheets leads data — sync 730 leads from Google Sheets into SQLite, display them in a Leads tab with filters and score pills, and surface aggregate counts (leads_totales, calificados) in the Resumen tab.
**Verified:** 2026-06-14T18:15:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Leads from the Google Sheet sync into SQLite via sync_sheets(db), on the hourly scheduler and the manual 'Sincronizar ahora' trigger | VERIFIED | `app/sync/jobs.py` line 234: `def sync_sheets(db: Session)` upserts by `sheet_row_id`. `app/sync/scheduler.py` line 12: `_run_all_syncs` calls both `sync_pipedrive` then `sync_sheets`. `app/routers/sync.py` line 13: `_run_sync_in_background` calls both syncs. |
| 2 | Each synced lead is classified by talent (exact name match, None for unmatched), source ('Gmail'), and status (verbatim Status_Filtrado including emoji) | VERIFIED | `app/sync/jobs.py` line 277: `talent_id = talent_map.get(row.talento_mencionado) if row.talento_mencionado else None`. Line 290: `existing.fuente = "Gmail"`. Line 289: `existing.status_filtrado = row.status_filtrado`. `QUALIFIED_STATUS = "✅ Aprobado - Respuesta enviada"` in `app/services/leads.py` line 13 uses exact emoji literal. |
| 3 | Re-running sync_sheets(db) is idempotent — second run inserts zero new rows (upsert by sheet_row_id) | VERIFIED | `app/sync/jobs.py` lines 279-283: query by `sheet_row_id`; if None, create new Lead and add; else update in place. `test_sync_sheets_idempotent` (test_leads.py line 257) asserts `count_after_first == count_after_second == 3`. Full test suite: 111 passed. |
| 4 | GET /leads/summary returns leads_totales and calificados counts and requires auth | VERIFIED | `app/routers/leads.py` line 55: `@router.get("/summary", response_model=LeadsSummary)`. Router declared with `dependencies=[Depends(get_current_user)]` (line 20). Tests `test_summary_requires_auth` and `test_summary_returns_200_with_auth` both pass. |
| 5 | The Leads tab displays all synced leads as a list with a colored Score_Calidad pill (0-40 red, 41-70 amber, 71-100 green) | VERIFIED (code) / HUMAN for rendering | `frontend/js/leads.js` line 22: `scorePillColor(score)` returns correct CSS var pairs per range. `renderLeadsList` line 153-154 applies the pill. `frontend/index.html` line 173: `id="page-leads"` with `id="leads-list"`. **Visual rendering requires human check.** |
| 6 | The Leads tab shows a 'Leads por talento' bar section with count and calificados per talent, including talents with zero leads | VERIFIED (code) / HUMAN for rendering | `app/services/leads.py` line 53: `leads_by_talent` uses `outerjoin` so talents with 0 leads appear with total=0. `frontend/js/leads.js` line 109: iterates `orderedBars` including zero-total talents. `id="leads-by-talent"` in index.html line 186. `test_talent_with_zero_leads_renders_zero` passes. |
| 7 | The leads list is filterable by talent, source, and status via GET /leads query params | VERIFIED | `app/routers/leads.py` line 24: `@router.get("", response_model=list[LeadRow])` with `talent_id`, `status`, `fuente` params. `app/services/leads.py` lines 120-125: three independent filter branches. `frontend/js/leads.js` lines 234-244: dropdown values build query string. Tests `test_leads_list_filter_talent`, `_filter_status`, `_filter_fuente` all pass. |
| 8 | GET /dashboard/summary includes leads_totales and calificados counts sourced from the leads table | VERIFIED | `app/schemas/dashboard.py` line 51-52: `leads_totales: int = 0`, `calificados: int = 0`. `app/routers/dashboard.py` line 54: `leads_data = leads_service.leads_summary(db)` called before `_has_data` check. Lines 62-63 and 84-85: both return paths pass `leads_totales` and `calificados`. `grep -c "leads_totales=" routers/dashboard.py` returns 2. |
| 9 | The Resumen tab shows wired-up 'Leads totales' and 'Calificados' KPI tiles with real counts | VERIFIED (code) / HUMAN for rendering | `frontend/index.html` lines 47-58: `id="leads-overview-grid"`, `id="leads-totales-val"`, `id="calificados-val"`. `frontend/js/dashboard.js` line 255: `renderLeadsOverviewKpis` sets both via `textContent`. Line 434: called before `has_data` branch — fires on both empty-state and data-loaded paths. **Visual rendering requires human check.** |

**Score:** 9/9 truths verified (all code verified; 3 truths have a human-check component for visual rendering)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py` | Lead SQLAlchemy model with sheet_row_id natural key | VERIFIED | `class Lead(Base)` lines 92-118; `sheet_row_id` mapped with `unique=True, index=True` |
| `app/integrations/sheets.py` | Read-only gspread client and get_leads_rows() | VERIFIED | `_client()` + `SheetLeadRow` + `get_leads_rows()`. Docstring states READ-ONLY. Zero write method calls in executable code (doc comment at line 3-4 describes what not to call; no `ws.update`/`ws.append_row` in callable code). |
| `app/services/leads.py` | QUALIFIED_STATUS constant, talent match, leads_summary, leads_by_talent, leads_list | VERIFIED | All 5 functions present: `QUALIFIED_STATUS`, `resolve_talent_id`, `leads_summary`, `leads_by_talent`, `leads_list`. `grep -c` returned 8 matches for these symbols. |
| `app/sync/jobs.py` | sync_sheets(db) upsert job with source='sheets' concurrency guard | VERIFIED | `def sync_sheets` line 234, `def _parse_fecha` line 219. Concurrency guard filters `SyncLog.source == "sheets"` AND `SyncLog.status == "running"`. |
| `app/routers/leads.py` | Auth-protected /leads router with GET /leads/summary and GET /leads | VERIFIED | `prefix="/leads"`, `dependencies=[Depends(get_current_user)]`. GET `""` (response_model=list[LeadRow]) and GET `/summary` (response_model=LeadsSummary). |
| `app/schemas/leads.py` | LeadRow, LeadsSummary, TalentLeadBar schemas | VERIFIED | All three classes defined with correct fields including `talent_name`, `status_display`, `por_talento`. |
| `app/schemas/dashboard.py` | DashboardSummary extended with leads_totales + calificados | VERIFIED | Lines 51-52: `leads_totales: int = 0`, `calificados: int = 0` with safe defaults. |
| `alembic/versions/d48d69b17ea6_add_leads_table.py` | Migration creating the leads table | VERIFIED | `op.create_table('leads', ...)`, `down_revision = 'c35f623eaa21'`, 3 indexes: `ix_leads_sheet_row_id` (unique), `ix_leads_talent_id`, `ix_leads_status_filtrado`. |
| `frontend/index.html` | Leads tab nav + #page-leads section + Resumen leads tiles | VERIFIED | Line 22: 4th tab `setPage('leads', event)`. Lines 173-215: `id="page-leads"` with kpi-grid, by-talent, filters, list. Lines 47-58: `id="leads-overview-grid"` with `leads-totales-val` and `calificados-val`. |
| `frontend/js/leads.js` | loadLeads, loadLeadsSummary, scorePillColor; escHtml reused, not redefined | VERIFIED | All 3 functions defined. `grep -c "function loadLeads\|function loadLeadsSummary\|function scorePillColor"` returns 3. `grep -c "function escHtml\|function apiFetch"` returns 0 (not redefined). `escHtml` used 10 times. |
| `frontend/js/dashboard.js` | leads branch in setPage + renderLeadsOverviewKpis | VERIFIED | Line 58-60: `else if (name === "leads") { loadLeadsSummary(); loadLeads(); }`. Line 255: `renderLeadsOverviewKpis`. Line 258-259: uses `textContent`. Line 434: called before `has_data` guard. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/sync/scheduler.py` | `app.sync.jobs.sync_sheets` | `_run_all_syncs` calls both syncs | WIRED | Line 7: `from app.sync.jobs import sync_pipedrive, sync_sheets`. Line 21: `sync_sheets(db)`. |
| `app/routers/sync.py` background task | `app.sync.jobs.sync_sheets` | `_run_sync_in_background` calls both syncs | WIRED | Line 8: `from app.sync.jobs import sync_pipedrive, sync_sheets`. Line 21: `sync_sheets(db)`. |
| `app/services/leads.py` | `app.models.Lead` | `leads_summary` and `leads_list` query Lead table | WIRED | Line 9: `from app.models import Lead, Talent`. Queries use `db.query(Lead)` and `db.query(func.count(Lead.id))`. |
| `app/main.py` | `app.routers.leads.router` | `include_router` before static mount | WIRED | Line 7: `from app.routers import dashboard, health, leads, sync, talents`. Line 25: `app.include_router(leads.router)`. Line 29: `app.mount(...)` comes after (line 25 < line 29). |
| `frontend/js/leads.js` | `/leads` | `apiFetch` in `loadLeads` | WIRED | Line 244: `apiFetch(\`/leads${qs}\`)`. Response handled and passed to `renderLeadsList`. |
| `frontend/js/leads.js` | `/leads/summary` | `apiFetch` in `loadLeadsSummary` | WIRED | Line 218: `apiFetch("/leads/summary")`. Response passed to `renderLeadsSummary` and `populateTalentFilter`. |
| `app/routers/leads.py` | `app.services.leads.leads_list` | `list_leads` delegates to service | WIRED | Line 51: `rows = leads_service.leads_list(db, ...)`. |
| `frontend/index.html` | `frontend/js/leads.js` | script tag after dashboard.js | WIRED | Line 219: `<script src="/js/leads.js"></script>` after dashboard.js at line 218. |
| `app/routers/dashboard.py` | `app.services.leads.leads_summary` | `get_summary` calls leads_service.leads_summary | WIRED | Line 32: `from app.services import leads as leads_service`. Line 54: `leads_data = leads_service.leads_summary(db)`. |
| `frontend/js/dashboard.js` | `/dashboard/summary` → `data.leads_totales` | `loadSummary` reads leads fields and calls renderLeadsOverviewKpis | WIRED | Line 434: `renderLeadsOverviewKpis(data.leads_totales ?? 0, data.calificados ?? 0)` — before the `has_data` guard at line 436, so fires on both branches. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `frontend/js/leads.js` | `data.por_talento` / `leads` | `/leads/summary` → `leads_service.leads_by_talent(db)` → `db.query(Talent).outerjoin(Lead)` | Yes — real DB query | FLOWING |
| `frontend/js/leads.js` | `leads` (list) | `/leads` → `leads_service.leads_list(db)` → `db.query(Lead).options(joinedload(Lead.talent))` | Yes — real DB query | FLOWING |
| `frontend/js/dashboard.js` | `data.leads_totales`, `data.calificados` | `/dashboard/summary` → `leads_service.leads_summary(db)` → `db.query(func.count(Lead.id))` | Yes — real DB count queries | FLOWING |
| `frontend/index.html` `#leads-totales-val` | textContent | `renderLeadsOverviewKpis(data.leads_totales ?? 0, ...)` | Yes — integer from DB | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `uv run pytest -x -q` | 111 passed, 1 warning in 5.27s | PASS |
| Leads + dashboard tests pass | `uv run pytest tests/test_leads.py tests/test_dashboard.py -x -q` | 59 passed in 1.21s | PASS |
| Lead model importable + migration applied | `uv run python -c "from app.models import Lead; ..."` | (migration file exists; 111 tests pass including DB operations) | PASS |
| sheets.py has zero write calls | `grep -n "ws\.update\|ws\.append_row\|..."` | Lines 3-4 are docstring comment only; no callable write code | PASS |
| QUALIFIED_STATUS exact emoji literal | `grep -F 'QUALIFIED_STATUS = "✅ Aprobado...' app/services/leads.py` | Matches line 13 | PASS |
| sync_sheets concurrency guard filters by source | `grep -F 'SyncLog.source == "sheets"'` | Matches line 249 of jobs.py | PASS |
| leads router registered before static mount | Line numbers in main.py | `include_router(leads.router)` at line 25; `app.mount` at line 29 | PASS |
| leads.js does not redefine apiFetch/escHtml | `grep -c "function escHtml\|function apiFetch" leads.js` | Returns 0 | PASS |
| escHtml used >= 4 times in leads.js | `grep -c "escHtml" leads.js` | Returns 10 | PASS |
| renderLeadsOverviewKpis uses textContent | `grep -n "textContent" dashboard.js` | Lines 258-259 in renderLeadsOverviewKpis use textContent | PASS |
| DashboardSummary has leads fields on both return paths | `grep -c "leads_totales=" routers/dashboard.py` | Returns 2 | PASS |

### Probe Execution

Step 7c: SKIPPED — No probe scripts exist in the repository; the phase does not declare probes in PLAN frontmatter.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| SHEET-01 | 03-01 | System syncs leads from Google Sheet into local SQLite | SATISFIED | `sync_sheets(db)` in `app/sync/jobs.py` upserts by `sheet_row_id`; wired to hourly scheduler and manual trigger; 6 sync tests pass. |
| SHEET-02 | 03-01, 03-02 | Leads classified by talent, source, and status | SATISFIED | `resolve_talent_id` (exact match), `fuente="Gmail"`, `status_filtrado` verbatim emoji. `STATUS_DISPLAY` map. `leads_by_talent` outerjoin with Sin-talento bucket. Filter endpoint with all three dimensions. |
| DASH-04 | 03-02, 03-03 | Leads Gmail — leads classified by talent, source, and status | SATISFIED | Leads tab (`#page-leads`) with filterable list and per-talent bars (03-02). Resumen tab `leads-overview-grid` tiles and `GET /dashboard/summary` leads fields (03-03). |

All 3 requirement IDs declared across the plans are accounted for. No orphaned requirements for Phase 3 detected in REQUIREMENTS.md.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/routers/sync.py` | 30-31 | Concurrency guard at the manual trigger level filters ANY running SyncLog (no source filter), so if a pipedrive sync is running, "Sincronizar ahora" returns `already_running` and skips the Sheets sync too | WARNING | A user who clicks "Sincronizar ahora" during an active Pipedrive sync will get no Sheets sync. The per-sync guards in `sync_sheets`/`sync_pipedrive` themselves are source-isolated; this is a pre-check at the router level that is source-unfiltered. Noted in memory as a known bug from Phase 2; not introduced by Phase 3. Not a blocker for phase goal. |

No `TBD`, `FIXME`, or `XXX` markers found in any Phase 3 modified files.
No stub patterns (empty returns, hardcoded placeholders) found in any implementation file.

### Human Verification Required

#### 1. Leads Tab Visual Rendering

**Test:** Open the dashboard in a browser, log in, click the "Leads" tab.
**Expected:** The "Leads por talento" section renders source-row bars with `{total} leads · {calificados} calificados` text. The leads list shows rows with colored score pills (red for 0-40, amber for 41-70, green for 71-100, grey for null). Status pills are colored by Aprobado/Bloqueado/En revisión.
**Why human:** CSS var() pair rendering and innerHTML interpolation via scorePillColor/statusPillStyle cannot be verified programmatically without a browser.

#### 2. Filter Dropdown Behavior

**Test:** On the Leads tab, select a talent from the "Todos los talentos" dropdown. Then select "Aprobado" from the status dropdown.
**Expected:** Each selection triggers a fetch to `/leads?talent_id=X` or `/leads?status=✅+Aprobado...` and the list re-renders showing only matching leads. Changing back to "Todos" restores the full list.
**Why human:** DOM event listener wiring and dynamic re-render require browser interaction.

#### 3. Resumen Tab Leads Tiles with Real Data

**Test:** On the Resumen tab after a sync has run, confirm "Leads totales" and "Calificados" tiles show real integer counts (not "--").
**Expected:** Tiles populated from `data.leads_totales` and `data.calificados` from `/dashboard/summary`, matching what the Leads tab KPI tiles show.
**Why human:** Tile content is set at runtime via textContent; requires visual confirmation after an actual sync.

#### 4. End-to-End Sync from Live Google Sheets

**Test:** With valid `GOOGLE_SERVICE_ACCOUNT_JSON` and `GOOGLE_SHEETS_ID` in environment, click "Sincronizar ahora". Check the Leads tab KPI tile "Leads totales" after sync completes.
**Expected:** Approximately 730 rows synced; "Leads totales" tile shows ~730. Re-clicking "Sincronizar ahora" does not change the count (idempotency confirmed end-to-end).
**Why human:** Requires live Google Sheets API credential and network access. Cannot be verified without external service connection.

### Gaps Summary

No blocking gaps found. All 9 must-have truths are code-verified. The 4 human verification items above are standard browser/credential checks that cannot be verified programmatically. One pre-existing WARNING (sync router source-unfiltered concurrency guard) is not introduced by Phase 3 and does not block the phase goal.

---

_Verified: 2026-06-14T18:15:00Z_
_Verifier: Claude (gsd-verifier)_
