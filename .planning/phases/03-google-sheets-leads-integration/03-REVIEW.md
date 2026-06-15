---
phase: 03-google-sheets-leads-integration
reviewed: 2026-06-14T18:10:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - alembic/versions/d48d69b17ea6_add_leads_table.py
  - app/integrations/sheets.py
  - app/main.py
  - app/models.py
  - app/routers/dashboard.py
  - app/routers/leads.py
  - app/routers/sync.py
  - app/schemas/dashboard.py
  - app/schemas/leads.py
  - app/services/leads.py
  - app/sync/jobs.py
  - app/sync/scheduler.py
  - frontend/index.html
  - frontend/js/dashboard.js
  - frontend/js/leads.js
  - pyproject.toml
  - tests/conftest.py
  - tests/test_dashboard.py
  - tests/test_leads.py
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-06-14T18:10:00Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 03 delivers the Google Sheets leads integration: a gspread read-only sync pipeline, a `Lead` model, service/router layers for lead querying, and frontend tab rendering. The core architecture is sound — the read-only constraint is respected in the integration layer, SQLAlchemy ORM is used consistently preventing SQL injection, and escHtml is applied to Sheet-sourced strings in leads.js. However, three blockers were found:

1. **sync_pipedrive has no source filter on its concurrency guard** — a running or stale `sheets` SyncLog permanently blocks the Pipedrive sync function, the opposite of what the code comment documents.
2. **Unescaped API data injected into innerHTML** — KPI tile labels (`tile.label`) and bottleneck stage names (`bottleneck.stage_a`, `bottleneck.stage_b`) are interpolated raw into innerHTML without escaping.
3. **Over-privileged Google Drive OAuth scope** — the service account is granted full read/write Drive access when read-only Sheets scope would suffice, violating the CLAUDE.md read-only constraint at the credential level.

Five additional warnings cover a stale-run deadlock in the manual sync router, incorrect calificados counting for the sin-talento bucket, a dead exported function, inaccurate test fixture data, and a config pitfall on empty env vars.

---

## Critical Issues

### CR-01: sync_pipedrive Concurrency Guard Has No Source Filter — Sheets Running Log Blocks Pipedrive Sync

**File:** `app/sync/jobs.py:49-54`
**Issue:** `sync_pipedrive`'s concurrency guard filters only on `SyncLog.status == "running"` with no `source` filter. `sync_sheets` (line 249) correctly filters by `SyncLog.source == "sheets"`. Since `_run_all_syncs` in `scheduler.py` calls `sync_pipedrive` then `sync_sheets` sequentially, a stale or crashed `sheets` SyncLog left in `status="running"` will permanently block `sync_pipedrive` on all subsequent hourly ticks. The code's own docstring ("Concurrency guard prevents two syncs running at once") and the comment in sync_sheets ("filter by source='sheets' only (Pitfall 6)") document that source-isolation is the intended behaviour — it was implemented in `sync_sheets` but not applied symmetrically to `sync_pipedrive`.

```python
# BEFORE (jobs.py line 49-50) — no source filter:
running = (
    db.query(SyncLog)
    .filter(SyncLog.status == "running")           # blocks on ANY source
    .order_by(SyncLog.started_at.desc())
    .first()
)

# AFTER — mirror the sheets guard pattern:
running = (
    db.query(SyncLog)
    .filter(SyncLog.source == "pipedrive", SyncLog.status == "running")
    .order_by(SyncLog.started_at.desc())
    .first()
)
```

---

### CR-02: Unescaped API-Sourced Strings Injected into innerHTML

**File:** `frontend/js/dashboard.js:272, 527, 411`

**Issue — KPI tile labels (lines 272 and 527):**
`tile.label` is interpolated directly into innerHTML in both `renderKpis()` and `renderKpisInto()` without `escHtml()`. Although current service-layer values are hardcoded strings, the `KpiTile` schema is a plain `BaseModel` populated from service dicts with no field-level sanitisation. If a future service adds a label sourced from external data (Pipedrive field name, talent name), a stored XSS payload would execute.

**Issue — Bottleneck stage names (line 411):**
`bottleneck.stage_a` and `bottleneck.stage_b` are interpolated raw. These values originate from `stage_name` in the `Deal` table, which is populated verbatim from the Pipedrive API (`jobs.py:184`). A Pipedrive stage name containing `<script>` or `<img onerror=...>` would execute in the user's browser.

```javascript
// BEFORE (line 272, 527):
<div class="kpi-label">${tile.label}</div>

// AFTER:
<div class="kpi-label">${escHtml(tile.label)}</div>

// BEFORE (line 411):
...solo el ${bottleneck.conversion_pct}% de los deals en ${bottleneck.stage_a} avanzan a ${bottleneck.stage_b}.

// AFTER:
...solo el ${escHtml(String(bottleneck.conversion_pct))}% de los deals en ${escHtml(bottleneck.stage_a)} avanzan a ${escHtml(bottleneck.stage_b)}.
```

---

### CR-03: Over-Privileged Google Drive OAuth Scope

**File:** `app/integrations/sheets.py:19-22`

**Issue:** The service account is granted `"https://www.googleapis.com/auth/drive"` — full read/write access to all Google Drive files owned or shared with the service account. CLAUDE.md explicitly states "READ-ONLY for all external integrations" and the integration only ever calls `ws.get_all_values()`. The Drive write scope directly contradicts this constraint and violates the principle of least privilege: a compromised service account JSON or a future accidental write call would have full Drive write access rather than being constrained by scope.

```python
# BEFORE:
_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# AFTER — read-only scopes only:
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]
```

The `spreadsheets.readonly` scope is sufficient for `gspread` to call `open_by_key()` and `get_all_values()`. The legacy `spreadsheets.google.com/feeds` scope can also be removed as `google-auth` 2.x uses the newer scope format.

---

## Warnings

### WR-01: sync Router Concurrency Guard Has No Source Filter and No Stale Check

**File:** `app/routers/sync.py:29-36`

**Issue:** The manual `POST /sync/pipedrive` endpoint checks for any `SyncLog.status == "running"` row regardless of `source` and returns `already_running` with no staleness timeout. This differs from both `sync_pipedrive` and `sync_sheets` in `jobs.py`, which call `_is_stale()` with a 1-hour timeout. Consequence: a stale `sheets` or `pipedrive` SyncLog (from a crashed background job) permanently blocks the "Sincronizar ahora" button until someone manually updates the DB row — the UI shows "Ya hay una sincronización en curso" indefinitely with no recovery path.

```python
# AFTER — add source filter and stale guard:
running = (
    db.query(SyncLog)
    .filter(SyncLog.source == "pipedrive", SyncLog.status == "running")
    .order_by(SyncLog.started_at.desc())
    .first()
)
from app.sync.jobs import _is_stale
if running is not None and not _is_stale(running):
    return SyncTriggerResponse(status="already_running")
```

---

### WR-02: Incorrect calificados Count for Sin-Talento Bucket

**File:** `app/services/leads.py:95`

**Issue:** The "Sin talento asignado" bucket hardcodes `"calificados": 0` with the comment "Can't be calificado without a talent." This is an incorrect assumption. The `Lead` model allows `talent_id IS NULL` and `status_filtrado == QUALIFIED_STATUS` simultaneously — a lead can be approved before a talent is matched to it. A scan of the live data comment (730 rows) does not rule this out. The hardcoded zero under-counts calificados when this situation occurs.

```python
# AFTER — count qualified leads with talent_id IS NULL:
sin_calificados = (
    db.query(func.count(Lead.id))
    .filter(Lead.talent_id.is_(None), Lead.status_filtrado == QUALIFIED_STATUS)
    .scalar() or 0
)
results.append({
    "talent_id": None,
    "name": "Sin talento asignado",
    "total": sin_count,
    "calificados": sin_calificados,
    "is_sin_talento": True,
})
```

---

### WR-03: resolve_talent_id Is Dead Code

**File:** `app/services/leads.py:23-32`

**Issue:** `resolve_talent_id()` is defined but never called anywhere in the application. `sync_sheets` in `jobs.py` performs talent resolution via a pre-built dict (`talent_map`) to avoid N+1 queries. `resolve_talent_id` does issue a per-call DB query and was presumably an earlier design. It is exported from `app.services.leads` and visible to importers, creating a misleading API surface.

```python
# Remove resolve_talent_id entirely, or mark private with _ prefix if kept for scripts.
# The talent_map pattern in sync_sheets (jobs.py:270-271) is the correct pattern.
```

---

### WR-04: mock_sheets_rows Fixture Has Incorrect bloqueado Value for Blocked Lead

**File:** `tests/conftest.py:448`

**Issue:** The `mock_sheets_rows` fixture sets `bloqueado=False` for the row with `status_filtrado="🚫 Remitente bloqueado"`. The `seed_leads` fixture correctly sets `bloqueado=True` for the equivalent row. When `sync_sheets` upserts the mock rows, the resulting `Lead.bloqueado` field is `False` for a record whose status says it is blocked — the two fields are inconsistent. No test currently asserts on `lead.bloqueado` for synced rows, so this passes silently, but the fixture is misleading and would cause failures if that assertion is added.

```python
# BEFORE (conftest.py line 448):
bloqueado=False,

# AFTER:
bloqueado=True,  # Consistent with status_filtrado="🚫 Remitente bloqueado"
```

---

### WR-05: mock_sheets_rows Talent Names Do Not Match seed_talent_products — Talent Resolution Is Never Integration-Tested

**File:** `tests/conftest.py:434, 446`

**Issue:** `mock_sheets_rows` uses `talento_mencionado="Emicanico"` and `talento_mencionado="Mariana"`, but `seed_talent_products` creates talents named `"Talento Uno"` and `"Talento Dos"`. Because `sync_sheets` resolves talent by exact name match, all three mock rows (including the two with named talents) resolve to `talent_id=None`. The tests `test_sync_sheets_inserts_rows` and `test_sync_sheets_idempotent` only assert `count==3` and `status=="success"` — the talent resolution code path is never exercised in the sync integration tests. A regression in talent name lookup would go undetected.

**Fix:** Add a talent whose name matches at least one `talento_mencionado` value in the fixture, then assert `lead.talent_id is not None` for that row:

```python
# Option A: align mock data with existing seed names
SheetLeadRow(..., talento_mencionado="Talento Uno", ...)

# Option B: add a matching talent in the fixture
talent_emicanico = Talent(name="Emicanico", active=True)
db_session.add(talent_emicanico)
db_session.commit()
# Then assert:
lead = db_session.query(Lead).filter(Lead.sheet_row_id == 2).first()
assert lead.talent_id == talent_emicanico.id
```

---

## Info

### IN-01: GOOGLE_SERVICE_ACCOUNT_JSON Empty-String Default Crashes at Runtime Without Helpful Message

**File:** `app/config.py:17`, `app/integrations/sheets.py:27`

**Issue:** `GOOGLE_SERVICE_ACCOUNT_JSON` defaults to `""` in `config.py`. When `_client()` is called during a sheets sync with an empty env var, `json.loads("")` raises `json.decoder.JSONDecodeError`, which propagates to `sync_sheets`' `except` block and writes a cryptic `"Expecting value: line 1 column 1 (char 0)"` message to `SyncLog.error_message`. There is no startup validation (unlike `SECRET_KEY` which fails fast at process start).

**Fix:** Add a `@field_validator` on `GOOGLE_SERVICE_ACCOUNT_JSON` in `config.py` to raise a descriptive error at startup if the field is empty when sheets integration is expected, or at minimum add a guard in `_client()`:

```python
# In _client():
if not settings.GOOGLE_SERVICE_ACCOUNT_JSON:
    raise RuntimeError(
        "GOOGLE_SERVICE_ACCOUNT_JSON env var is empty. "
        "Set it to the service account JSON string."
    )
```

---

### IN-02: pyproject.toml Declares rapidfuzz as a Runtime Dependency but It Is Only Used in a Script

**File:** `pyproject.toml:19`

**Issue:** `rapidfuzz>=3.14.5` is listed under `[project] dependencies` (runtime), but its only usage is in `app/scripts/match_talent_products.py` — a one-off data migration script. This increases the production Docker image size unnecessarily.

**Fix:** Move to `[dependency-groups] dev` or create a `scripts` group, or install it only in the environment where the script is run. Since it is not imported by any router, service, or integration module, omitting it from the runtime image is safe.

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.3",
    "rapidfuzz>=3.14.5",  # only used in app/scripts/
    "respx>=0.23.1",
    "ruff>=0.15.17",
]
```

---

### IN-03: gspread Creates a New HTTP Client on Every Sync Call

**File:** `app/integrations/sheets.py:25-29`

**Issue:** `_client()` is called once per `sync_sheets` invocation and constructs a new `gspread.Client` (including credential setup and auth token fetch) each time. For the current hourly schedule this is acceptable, but `gspread.Client` objects are reusable across calls and holding one at module level (with credential refresh handled by `google-auth`) would eliminate unnecessary auth round-trips and improve resilience against transient auth errors.

**Fix (optional for current scale):** Cache the client at module level with lazy initialization:

```python
_cached_client: gspread.Client | None = None

def _get_or_create_client() -> gspread.Client:
    global _cached_client
    if _cached_client is None:
        sa_info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = Credentials.from_service_account_info(sa_info, scopes=_SCOPES)
        _cached_client = gspread.authorize(creds)
    return _cached_client
```

---

_Reviewed: 2026-06-14T18:10:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
