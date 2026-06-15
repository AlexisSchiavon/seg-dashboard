# Phase 3: Google Sheets Leads Integration - Research

**Researched:** 2026-06-14
**Domain:** Google Sheets ingestion via gspread, SQLAlchemy model extension, leads service and router
**Confidence:** HIGH — all findings verified against live Sheet data and existing codebase

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-29:** Auth via `GOOGLE_SERVICE_ACCOUNT_JSON` env var using `gspread.service_account_from_dict()`. Sheet already exists with real data — no schema design needed.

**D-30:** Sync only the 10 core columns: `ID_Lead`, `Remitente_Nombre`, `Remitente_Email`, `Asunto`, `Fecha_Recepcion`, `Talento_Mencionado`, `Status_Filtrado`, `Score_Calidad`, `Bloqueado`, `Convertido_a_Prospecto`. The 8 remaining columns (`Email_Completo`, `Categoria_Detectada`, `Razon_validacion`, `Respuesta_Enviada`, `Fecha_Respuesta`, `Link_WhatsApp_Generado`, `ID_Prospecto`, `Threadid`) are ignored for now.

**D-31:** Sync frequency: same pattern as Pipedrive — hourly automatic sync + manual "Sincronizar ahora" button. Sheets sync runs as part of the same scheduler job.

**D-32:** Talent attribution from `Talento_Mencionado`. Match strategy: name-based exact/near-exact match against `talent.name` in DB. No alias table needed.

**D-33:** Leads with empty or unmatched `Talento_Mencionado` are still synced and grouped under "Sin talento asignado" bucket. Count in global totals, not per-talent KPIs.

**D-34:** Distinct `Status_Filtrado` values must be enumerated from live Sheet before planning. **RESOLVED — see Live Sheet Analysis below.**

**D-35:** `fuente` field stored explicitly, defaults to `"Gmail"` for all Phase 3 leads.

**D-36:** `Score_Calidad` displayed as colored pill: 0–40 → red (`--redT`), 41–70 → amber (`--amberT`), 71–100 → green (`--greenT`).

**D-37:** Phase 3 wires up "Leads totales" and "Calificados" KPI tiles on Resumen tab (previously placeholders per D-28).

**D-38:** Definition of "Calificado" delegated to researcher. **RESOLVED — see Calificado Definition below.**

### Claude's Discretion

- "Leads por talento" bar section sorting (by total leads vs. qualified count) and pagination (show all vs. top N) — follow mockup reference.
- `Bloqueado` and `Convertido_a_Prospecto` fields: synced but not yet surfaced in the UI. Visual treatment (subtle pill, greyed-out state) is planner's call.
- Filtering depth: dropdown vs. chip-based, URL-param state — follow Vanilla JS patterns already in `dashboard.js`.

### Deferred Ideas (OUT OF SCOPE)

- `Categoria_Detectada` column mapping to brand category (Phase 4/5).
- `ID_Prospecto` linkage to Pipedrive deals (cross-source conversion tracking, future phase).
- `Link_WhatsApp_Generado` outreach status view (future phase).
- `Bloqueado` and `Respuesta_Enviada` filtering facets (Phase 4/5).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SHEET-01 | System syncs leads from a Google Sheet (fed by Gmail) into local SQLite | gspread `get_all_values()` verified at 0.40s for 730 rows; hourly scheduler hook identified in `app/sync/scheduler.py` |
| SHEET-02 | Leads are classified by talent, source, and status | All 12 Sheet talent names match DB names exactly; 3 Status_Filtrado values enumerated; `fuente="Gmail"` covers source |
| DASH-04 | Leads Gmail tab — leads classified by talent, source, and status | Mockup `#page-leads` structure fully mapped; KPI tiles, per-talent bars, lead list patterns identified |
| DASH-01 (partial) | Resumen tab "Leads totales" and "Calificados" KPI tiles wired up | `global_kpis()` extension point in `app/services/kpis.py`; tiles already rendered in HTML mockup |
</phase_requirements>

---

## Summary

The Google Sheet "Talent Agency base de datos automatizacion" (Leads worksheet) has 730 data rows spanning 2026-03-30 to 2026-06-14 across exactly 18 columns matching the D-30 specification verbatim. All live data was fetched and analyzed via `gspread.get_all_values()` in a single call taking 0.40 seconds. The integration is straightforward: one gspread call, column-index extraction for the 10 core fields, row-position-based natural key (since `ID_Lead` is uniformly empty in the live data), and upsert into a new `leads` table.

The three `Status_Filtrado` values are now confirmed: `"🚫 Remitente bloqueado"` (54%), `"✅ Aprobado - Respuesta enviada"` (30%), and `"En revisión"` (16%). "Calificado" maps unambiguously to `"✅ Aprobado - Respuesta enviada"`. The `Score_Calidad` range is 0–100 with no out-of-range values, confirming D-36's three-bucket color scheme. All 12 talent names in the Sheet are exact-string matches to the canonical `Talentos` sheet and therefore to the DB `talents` table populated from the same source.

One critical discovery: `ID_Lead` is empty for all 730 rows — the column exists in the header but is never populated by the automation. The natural key for upsert must be derived from row position in the sheet (sheet row number = data-row index + 2). A second significant finding: 25 distinct email+subject combinations appear in rows assigned to multiple different talents, meaning a single inbound email is fanned out as multiple rows (one per potential talent). Each row is an independent lead record with its own talent assignment, status, and score.

**Primary recommendation:** Use sheet row number as `sheet_row_id` (the stable natural key). Implement `app/integrations/sheets.py` mirroring the `pipedrive.py` pattern (typed Pydantic models, no raw dicts), `app/services/leads.py` for classification logic, and `app/routers/leads.py` for the protected Leads tab endpoints. Hook sheets sync into the existing APScheduler job alongside `sync_pipedrive`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fetch Sheet rows | API / Backend (`sheets.py`) | — | gspread is a server-side library; browser cannot call Sheets API directly (CORS, credential exposure) |
| Talent name matching | API / Backend (`leads.py`) | — | Requires DB lookup against `talents` table; belongs in the service layer, not the router |
| Status taxonomy / Calificado rule | API / Backend (`leads.py`) constant | — | Business logic; must not live in JS or the router |
| Score pill color logic | Browser / Client (JS + CSS vars) | — | Pure UI mapping (`0-40 → --redT`, etc.); no server round-trip needed once score is in the response |
| Hourly sync scheduling | API / Backend (`scheduler.py`) | — | APScheduler is already wired into FastAPI lifespan; same pattern as Pipedrive |
| Leads totales / Calificados KPIs | API / Backend (`kpis.py`) | — | Extends existing `global_kpis()` function; dashboard router already calls this |
| Leads tab UI | Browser / Client (Vanilla JS) | — | Follows existing `dashboard.js` patterns; fetch from `/leads` endpoint |

---

## Live Sheet Analysis

**[VERIFIED: live gspread connection, 2026-06-14]**

### Sheet Metadata

| Property | Value |
|----------|-------|
| Spreadsheet title | "Talent Agency base de datos automatizacion" |
| Target worksheet | "Leads" |
| Total data rows | 730 |
| Date range | 2026-03-30 to 2026-06-14 |
| gspread fetch latency | 0.40s (`get_all_values()`, single API call) |
| Other worksheets | Métricas, Auditoria_Aprobados, Auditoria_Gmail_Sheets, Auditoria_NuevoModelo, Talentos |

### Column Headers (Exact, In Order)

Verified against D-30 specification. Header row position: row 1.

| Col # | Column Name | D-30 Status | Notes |
|-------|-------------|-------------|-------|
| 1 | `ID_Lead` | Core (sync) | **EMPTY in all 730 rows** — not usable as natural key |
| 2 | `Email_Completo` | Ignored | Contains full email body text (very long strings) |
| 3 | `Remitente_Email` | Core (sync) | Sender email address |
| 4 | `Remitente_Nombre` | Core (sync) | Sender display name |
| 5 | `Asunto` | Core (sync) | Email subject line |
| 6 | `Fecha_Recepcion` | Core (sync) | ISO 8601 format, mixed variants (with/without milliseconds, with/without timezone suffix) |
| 7 | `Talento_Mencionado` | Core (sync) | Talent name — exact match to DB in all observed values |
| 8 | `Status_Filtrado` | Core (sync) | 3 distinct values, see below |
| 9 | `Categoria_Detectada` | Ignored | "Spam", "B2B Válido", "Sin categoría", "Educación", "Creador de Contenido" |
| 10 | `Razon_validacion` | Ignored | Free-text AI explanation |
| 11 | `Score_Calidad` | Core (sync) | Integer 0–100, populated for all 730 rows |
| 12 | `Bloqueado` | Core (sync) | Values: `""` (393 rows) or `"FALSE"` (337 rows). No `"TRUE"` observed. |
| 13 | `Respuesta_Enviada` | Ignored | "TRUE" or "" |
| 14 | `Fecha_Respuesta` | Ignored | ISO 8601 with timezone offset |
| 15 | `Link_WhatsApp_Generado` | Ignored | WhatsApp deeplink URL |
| 16 | `Convertido_a_Prospecto` | Core (sync) | **Empty for all 730 rows** — sync as `False` |
| 17 | `ID_Prospecto` | Ignored | Empty for all 730 rows |
| 18 | `Threadid` | Ignored | Gmail thread ID — populated for 337/730 rows; NOT suitable as sole natural key |

**Column order matches D-30 specification exactly.** The only discrepancy from the spec's implied ordering is that columns 3 and 4 are `Remitente_Email` then `Remitente_Nombre` (spec listed them reversed), but both names match. Extract by column name index, not positional offset, to be robust.

### Status_Filtrado Distinct Values

**[VERIFIED: enumerated from all 730 live rows]**

| Exact Value | Count | Pct | Score Range | Avg Score |
|-------------|-------|-----|-------------|-----------|
| `"🚫 Remitente bloqueado"` | 393 | 53.8% | 0–45 | 18.3 |
| `"✅ Aprobado - Respuesta enviada"` | 218 | 29.9% | 35–100 | 75.4 |
| `"En revisión"` | 119 | 16.3% | 20–100 | 37.3 |

**Important:** These values include emoji characters. The Python constant definitions must use the exact Unicode strings including the emoji. String comparison in SQL (`WHERE status_filtrado = ?`) will work correctly since SQLite stores UTF-8.

### Score_Calidad Range

**[VERIFIED: computed from all 730 live rows]**

| Metric | Value |
|--------|-------|
| Minimum | 0 |
| Maximum | 100 |
| Mean | 38.4 |
| Out-of-range values | 0 (range confirmed 0–100) |
| Empty values | 0 (fully populated) |
| Distribution 0–40 (red) | 510 rows (69.9%) |
| Distribution 41–70 (amber) | 81 rows (11.1%) |
| Distribution 71–100 (green) | 139 rows (19.0%) |

D-36 thresholds (0–40 red / 41–70 amber / 71–100 green) are confirmed valid against live data.

---

## Calificado Definition

**[VERIFIED: derived from live Status_Filtrado x Score_Calidad cross-tab]**

**"Calificado" = `Status_Filtrado == "✅ Aprobado - Respuesta enviada"`**

Rationale from live data evidence:
- This status has an average Score_Calidad of 75.4 (vs. 18.3 for blocked, 37.3 for "En revisión").
- Score range for Approved is 35–100 — all high-quality signals.
- The status name itself indicates a response was sent to a legitimate inbound lead.
- "En revisión" leads are not yet qualified — they are pending human review.
- "🚫 Remitente bloqueado" leads are explicitly disqualified (spam, casino, prohibited industries).

**Planner action:** Define this as a module-level constant in `app/services/leads.py`:

```python
# app/services/leads.py
QUALIFIED_STATUS = "✅ Aprobado - Respuesta enviada"

# UI display mapping (for router response serialization)
STATUS_DISPLAY = {
    "✅ Aprobado - Respuesta enviada": "Aprobado",
    "🚫 Remitente bloqueado": "Bloqueado",
    "En revisión": "En revisión",
}
```

The raw `status_filtrado` value is stored in SQLite as-is (emoji included). The display label is computed at the API layer, not stored.

---

## Talent Match Analysis

**[VERIFIED: all 12 Sheet talent values compared against Talentos worksheet and DB seeds]**

### Exact Match Confirmation

All talent names in `Talento_Mencionado` are exact string matches to DB talent names. No fuzzy matching, normalization, or alias table is needed for the current data.

| Sheet Value | DB Match | Status |
|-------------|----------|--------|
| `"Emicanico"` | `"Emicanico"` | EXACT |
| `"Navarretes show"` | `"Navarretes show"` | EXACT |
| `"Mariana"` | `"Mariana"` | EXACT |
| `"Reborujados"` | `"Reborujados"` | EXACT |
| `"Mamamecanic"` | `"Mamamecanic"` | EXACT |
| `"Tony Franco"` | `"Tony Franco"` | EXACT |
| `"Don Silverio"` | `"Don Silverio"` | EXACT |
| `"Edgar"` | `"Edgar"` | EXACT |
| `"Ale"` | `"Ale"` | EXACT |
| `"Casandra Salinas"` | `"Casandra Salinas"` | EXACT |
| `"Deliberración"` | `"Deliberración"` | EXACT (accent on double-r: "rr") |
| `"Doc Fitness"` | `"Doc Fitness"` | EXACT |

### Talents with Zero Leads (in Sheet)

9 DB talents appear in no Sheet rows — they will show `0` leads in the "Leads por talento" section:

`Don Wicho`, `Abelito`, `Alan Lopez`, `Karamella`, `Elisa`, `Dulce`, `Victor Halfon`, `Lalo escalante`, `Moni`

These talents should still render in the per-talent bars section with zero counts rather than being hidden.

### Match Implementation

```python
# app/services/leads.py
def resolve_talent_id(db: Session, talent_name: str) -> int | None:
    """Exact-match lookup. Returns None for empty or unmatched names (D-33)."""
    if not talent_name or not talent_name.strip():
        return None
    talent = db.query(Talent).filter(Talent.name == talent_name.strip()).first()
    return talent.id if talent else None
```

The D-32 decision says "exact/near-exact" — given 100% exact match in live data, implement exact-only first. Near-exact (e.g., Levenshtein) can be added if new talents show name drift.

---

## Critical Finding: ID_Lead Is Empty — Natural Key Strategy

**[VERIFIED: all 730 ID_Lead cells are empty strings]**

The CONTEXT.md (D-30) specified `ID_Lead` as the upsert natural key (`sheet_lead_id`). **This is not viable — the column is populated by the Sheet automation but is currently empty for all 730 rows.**

### Revised Natural Key: Sheet Row Number

The sheet row number (data row index + 2, since row 1 is the header) is stable as long as the Sheet automation appends rows and never reorders or deletes them. This matches observed behavior (rows are append-only, date-sorted ascending).

```python
# sheet_row_id = row index in data list + 2
# Row 2 = first data row, row 731 = last current data row
for row_num, row in enumerate(all_rows, start=2):
    sheet_row_id = row_num
    # upsert by sheet_row_id
```

**Model field:** `sheet_row_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)`

**Risk:** If the Sheet automation ever inserts rows in the middle (not just appends), row numbers shift and all subsequent rows would be treated as updated. This is LOW risk given the append-only pattern observed, but should be documented in a code comment.

**Alternative (if row-number instability is a concern):** Use `(Remitente_Email, Asunto, Talento_Mencionado)` as a composite unique key. This has 47 duplicates in the current 730-row dataset (intentional — same email fanned out to multiple talents), so it would deduplicate rather than preserve all rows. **Do not use this — it loses the per-talent row semantics.**

**Recommended:** Sheet row number as `sheet_row_id`. Document the assumption in the model.

---

## Multi-Talent Fan-Out Pattern

**[VERIFIED: observed in live data]**

25 distinct `(Remitente_Email, Asunto)` combinations appear as rows assigned to multiple different talents. This is intentional: the Gmail automation routes one inbound email to multiple relevant talents and creates one row per talent.

Example: `vicky@asmkol.com` / `"Invitación de colaboración pagada en TikTok"` → rows for both `"Edgar"` and `"Tony Franco"`.

**Implication for the Lead model and sync:** Each row is an independent lead record. The composite of `(Remitente_Email, Asunto, Talento_Mencionado)` is NOT unique (47 pairs seen) — some emails appear twice for the same talent. Use sheet row number as the sole natural key.

**Implication for "Leads por talento" UI:** The count shown per talent is the count of rows assigned to that talent (not unique sender emails). This is correct behavior — it reflects how many engagement opportunities each talent has.

---

## gspread Implementation Notes

**[VERIFIED: gspread>=6.1, google-auth>=2.40 per STACK.md; tested against live sheet]**

### Auth Pattern

```python
# app/integrations/sheets.py
import json
import gspread
from google.oauth2.service_account import Credentials

from app.config import settings

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

def _client() -> gspread.Client:
    """Create an authenticated gspread client from settings.GOOGLE_SERVICE_ACCOUNT_JSON."""
    sa_info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = Credentials.from_service_account_info(sa_info, scopes=_SCOPES)
    return gspread.authorize(creds)
```

Note: `gspread.service_account_from_dict()` is the gspread-native convenience wrapper. Either pattern works — `Credentials.from_service_account_info` + `gspread.authorize()` is slightly more explicit about scopes.

### Data Fetch Pattern

```python
def get_leads_rows() -> list[dict]:
    """Fetch all data rows from the Leads worksheet.

    Returns list of dicts keyed by column name, with sheet_row_id injected.
    Single API call via get_all_values() — ~0.40s for 730 rows.
    """
    gc = _client()
    sh = gc.open_by_key(settings.GOOGLE_SHEETS_ID)
    ws = sh.worksheet("Leads")
    all_values = ws.get_all_values()

    if not all_values:
        return []

    headers = all_values[0]
    rows = []
    for row_idx, row in enumerate(all_values[1:], start=2):
        # Pad short rows to header length (gspread omits trailing empty cells)
        padded = row + [""] * (len(headers) - len(row))
        row_dict = dict(zip(headers, padded))
        row_dict["_sheet_row_id"] = row_idx
        rows.append(row_dict)
    return rows
```

**Padding note:** gspread's `get_all_values()` omits trailing empty cells on a row. If a row has 15 of 18 cells populated, it returns 15 values. Always pad to header length before zipping. Verified necessary: some rows in the live sheet have trailing empty cells.

### Pydantic Row Model

```python
from datetime import datetime
from pydantic import BaseModel, field_validator

class SheetLeadRow(BaseModel):
    sheet_row_id: int
    remitente_email: str
    remitente_nombre: str
    asunto: str
    fecha_recepcion: str  # Keep as string; parse in sync job with fallback
    talento_mencionado: str
    status_filtrado: str
    score_calidad: int | None
    bloqueado: bool
    convertido_a_prospecto: bool

    @field_validator("score_calidad", mode="before")
    @classmethod
    def parse_score(cls, v):
        if v == "" or v is None:
            return None
        try:
            return int(float(v))
        except (ValueError, TypeError):
            return None

    @field_validator("bloqueado", mode="before")
    @classmethod
    def parse_bool(cls, v):
        return str(v).upper() == "TRUE"

    @field_validator("convertido_a_prospecto", mode="before")
    @classmethod
    def parse_convertido(cls, v):
        return str(v).upper() == "TRUE"
```

**`Fecha_Recepcion` format inconsistency:** Live data has two variants:
- `"2026-03-30T17:39:37Z"` (no milliseconds)
- `"2026-03-30T17:45:02.000Z"` (with milliseconds)

Parse with `datetime.fromisoformat()` after stripping the trailing `Z` and replacing with `+00:00`, or use `dateutil.parser.parse()`. Store as `String` in SQLite (consistent with `Deal.update_time` pattern) or as `DateTime`. **Recommended:** store as `DateTime` (UTC-normalized) since Phase 5 reports will need date filtering.

---

## Integration Architecture

```
Google Sheets API
       |
       v (gspread.get_all_values(), ~0.40s, single call)
app/integrations/sheets.py
  get_leads_rows() -> list[SheetLeadRow]
       |
       v
app/sync/jobs.py :: sync_sheets(db)
  - Fetch all rows via sheets.get_leads_rows()
  - For each row: resolve talent_id via exact name match
  - Upsert Lead by sheet_row_id
  - Update SyncLog(source="sheets")
       |
       v
SQLite: leads table
       |
       v
app/services/leads.py
  leads_summary(db) -> totals, calificados count
  leads_by_talent(db) -> [{talent, total, calificados}]
  leads_list(db, filters) -> [Lead + talent_name]
       |
       v
app/routers/leads.py
  GET /leads          -> list of leads (paginated, filterable)
  GET /leads/summary  -> KPI tiles + per-talent bars
       |
       v
app/routers/dashboard.py :: get_summary()
  (extended to include leads_totales + calificados from leads_summary())
```

### Scheduler Hook

```python
# app/sync/scheduler.py — extend existing job
from app.sync.jobs import sync_pipedrive, sync_sheets  # new import

def _run_all_syncs():
    db = SessionLocal()
    try:
        sync_pipedrive(db)
        sync_sheets(db)
    finally:
        db.close()

# Replace _run_pipedrive_sync with _run_all_syncs in scheduler.add_job
```

**Decision point for planner:** Run sheets sync in the same job function as Pipedrive (sequential, simpler, single SyncLog per cycle) OR as a separate scheduled job (independent failure isolation, separate SyncLog). Given the low complexity, sequential in the same job is recommended. The `SyncLog.source` field can be `"sheets"` for a separate log row written by `sync_sheets()`.

### Router Pattern (mirrors dashboard.py)

```python
# app/routers/leads.py
router = APIRouter(
    prefix="/leads",
    tags=["leads"],
    dependencies=[Depends(get_current_user)],  # Same auth as other routers
)

@router.get("/summary", response_model=LeadsSummary)
def get_leads_summary(db: Session = Depends(get_db)):
    ...

@router.get("", response_model=list[LeadRow])
def list_leads(
    talent_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    ...
```

---

## Standard Stack

### Core (already in project)

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| `gspread` | `>=6.1,<7.0` (6.2.1) | Google Sheets API wrapper | In pyproject.toml per STACK.md |
| `google-auth` | `>=2.40,<3.0` (2.53.0) | Service account credentials | In pyproject.toml per STACK.md |
| `SQLAlchemy` | 2.0.x | ORM — new `leads` table + Alembic migration | Already in use |
| `Alembic` | 1.18.x | DB migration for `leads` table | Already in use |
| `Pydantic` v2 | ships with FastAPI | `SheetLeadRow` validation model | Already in use |
| `FastAPI` | 0.136.x | New `leads` router | Already in use |

**No new packages required for Phase 3.** All dependencies are already declared.

---

## Package Legitimacy Audit

No new packages are installed in this phase. `gspread` and `google-auth` were already evaluated in Phase 1/2 STACK.md research.

| Package | Registry | Age | Downloads | slopcheck | Disposition |
|---------|----------|-----|-----------|-----------|-------------|
| `gspread` | PyPI | 13+ yrs | High | N/A (pre-verified in STACK.md) | Approved |
| `google-auth` | PyPI | 8+ yrs | Very high | N/A (pre-verified in STACK.md) | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### Recommended Project Structure (Phase 3 additions)

```
app/
├── integrations/
│   ├── base.py              (existing)
│   ├── pipedrive.py         (existing)
│   └── sheets.py            (NEW — gspread wrapper, SheetLeadRow Pydantic model)
├── services/
│   ├── funnel.py            (existing)
│   ├── kpis.py              (existing — extend global_kpis() for leads KPIs)
│   └── leads.py             (NEW — talent match, status constants, query functions)
├── routers/
│   ├── dashboard.py         (existing — extend get_summary() for Leads totales/Calificados)
│   └── leads.py             (NEW — /leads and /leads/summary endpoints)
├── schemas/
│   └── leads.py             (NEW — LeadRow, LeadsSummary Pydantic response models)
├── sync/
│   ├── jobs.py              (existing — add sync_sheets() function)
│   └── scheduler.py         (existing — update to run sheets sync alongside Pipedrive)
├── models.py                (existing — add Lead model)
└── main.py                  (existing — register leads router)
alembic/versions/
└── XXXX_add_leads_table.py  (NEW — Alembic migration)
tests/
├── conftest.py              (existing — add seed_leads fixture)
└── test_leads.py            (NEW — unit + integration tests)
frontend/js/
└── leads.js                 (NEW or inline — Leads tab fetch + render)
```

### Pattern: Sync Job (mirrors sync_pipedrive)

```python
# app/sync/jobs.py — new function
def sync_sheets(db: Session) -> SyncLog:
    """Sync leads from Google Sheets into the local Lead table.

    Natural key: sheet_row_id (row number in Leads worksheet, header=row 1).
    All rows upserted on every full sync (no incremental filter available in Sheets).
    """
    # Concurrency guard: check for existing running sheets sync
    running = (
        db.query(SyncLog)
        .filter(SyncLog.source == "sheets", SyncLog.status == "running")
        .order_by(SyncLog.started_at.desc())
        .first()
    )
    if running is not None and not _is_stale(running):
        return running

    sync_log = SyncLog(
        source="sheets",
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db.add(sync_log)
    db.commit()
    db.refresh(sync_log)

    try:
        rows = sheets.get_leads_rows()  # Single API call

        # Build talent name -> id map (avoid N+1 queries)
        talent_map: dict[str, int] = {
            t.name: t.id for t in db.query(Talent).all()
        }

        records_synced = 0
        for row in rows:
            talent_id = talent_map.get(row.talento_mencionado)  # None = Sin talento
            existing = db.query(Lead).filter(
                Lead.sheet_row_id == row.sheet_row_id
            ).first()
            if existing is None:
                existing = Lead(sheet_row_id=row.sheet_row_id)
                db.add(existing)

            existing.remitente_email = row.remitente_email
            existing.remitente_nombre = row.remitente_nombre
            existing.asunto = row.asunto
            existing.fecha_recepcion = _parse_fecha(row.fecha_recepcion)
            existing.talent_id = talent_id
            existing.status_filtrado = row.status_filtrado
            existing.fuente = "Gmail"
            existing.score_calidad = row.score_calidad
            existing.bloqueado = row.bloqueado
            existing.convertido_a_prospecto = row.convertido_a_prospecto
            records_synced += 1

        db.commit()
        sync_log.status = "success"
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.records_synced = records_synced
        db.commit()

    except Exception as exc:
        db.rollback()
        sync_log.status = "error"
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.error_message = str(exc)  # Never log gspread response objects (may contain SA key)
        db.commit()

    return sync_log
```

### Pattern: Lead SQLAlchemy Model

```python
# app/models.py — add to existing file
class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Natural key: sheet row number (header=row 1, first data row=2)
    # Empty ID_Lead column in live data makes row number the only stable key.
    sheet_row_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)

    remitente_email: Mapped[str] = mapped_column(String)
    remitente_nombre: Mapped[str] = mapped_column(String, default="")
    asunto: Mapped[str] = mapped_column(String, default="")
    fecha_recepcion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # D-32: nullable FK — None = "Sin talento asignado" (D-33)
    talent_id: Mapped[int | None] = mapped_column(ForeignKey("talents.id"), nullable=True, index=True)

    status_filtrado: Mapped[str] = mapped_column(String, index=True)
    fuente: Mapped[str] = mapped_column(String, default="Gmail")  # D-35
    score_calidad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bloqueado: Mapped[bool] = mapped_column(Boolean, default=False)
    convertido_a_prospecto: Mapped[bool] = mapped_column(Boolean, default=False)

    talent: Mapped["Talent | None"] = relationship("Talent", lazy="select")
```

### Anti-Patterns to Avoid

- **Storing emoji in constants as escaped sequences:** Use the literal emoji characters `"✅"` and `"🚫"` in the Python constant. SQLite handles UTF-8; escaped `\U0001F6AB` is harder to read and match.
- **Using `Categoria_Detectada` as the status display label:** The UI category is `Status_Filtrado`. Do not substitute `Categoria_Detectada` (which is about brand validation, not lead status).
- **Treating Bloqueado=empty as False and Bloqueado=FALSE as True:** Both represent non-blocked. `"FALSE"` in Sheets is the string literal — it means the automation explicitly set blocked=False. Empty means the field was never written (also not blocked). Map both to `bloqueado=False` in the model. Only `"TRUE"` would mean blocked (not observed in live data).
- **Assuming ID_Lead will be populated in the future:** The automation writes Gmail thread IDs to `Threadid` (partially, 337/730 rows) and leaves `ID_Lead` empty. Do not build infrastructure expecting `ID_Lead` to become the key.
- **N+1 talent lookups:** Pre-build the `talent_name -> id` dict once per sync run, not per row.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Google auth token refresh | Manual OAuth2 token management | `google-auth` credential objects (auto-refresh) | `Credentials.from_service_account_info` handles token refresh internally |
| ISO 8601 date parsing with varied formats | Custom regex parser | `datetime.fromisoformat()` (Python 3.11+) or `dateutil.parser.parse()` | Live data has two timestamp variants; stdlib handles both in Python 3.11; use dateutil if needed |
| Paginated Sheet reads | Manual offset/limit | `ws.get_all_values()` | gspread fetches the entire sheet in one API call; 730 rows at 0.40s — no pagination needed |
| Case-insensitive talent matching | Custom normalize function | Exact string match (sufficient for live data) | All 12 talent names are exact matches — YAGNI |

**Key insight:** The Sheet integration is simpler than Pipedrive because (1) no pagination, (2) no custom field resolution, (3) no incremental sync filter (always full refresh), and (4) talent matching is exact-string rather than product-ID lookup. The main complexity is the natural key problem (solved by row number) and the `Fecha_Recepcion` format variants.

---

## Common Pitfalls

### Pitfall 1: ID_Lead Is Empty — Wrong Natural Key

**What goes wrong:** Code uses `ID_Lead` as the upsert key (`WHERE sheet_lead_id = ?`). Since all values are empty string, every sync inserts 730 new rows instead of upserting.

**Why it happens:** CONTEXT.md D-30 mentioned `ID_Lead` as the upsert key before live data was inspected.

**How to avoid:** Use `sheet_row_id` (row number in the worksheet) as the unique key. The `ID_Lead` column in the Sheet is unpopulated by the current automation.

**Warning signs:** `leads` table grows by 730 rows on every sync run.

### Pitfall 2: gspread Row Padding — IndexError on Short Rows

**What goes wrong:** `row[10]` raises `IndexError` for rows where trailing empty cells were omitted by gspread.

**Why it happens:** `get_all_values()` strips trailing empty strings from each row. A row with no value in columns 12–18 will have len < 18.

**How to avoid:** Always pad each row to header length before processing:
```python
padded = row + [""] * (len(headers) - len(row))
```

**Warning signs:** `IndexError` or `list index out of range` in the sync job on specific rows.

### Pitfall 3: Emoji in Status String Comparisons

**What goes wrong:** Python string `"Aprobado"` != `"✅ Aprobado - Respuesta enviada"`. A naive substring check or stripped comparison breaks the Calificado filter.

**Why it happens:** Developers copy-paste the label without the emoji prefix.

**How to avoid:** Define the constant once:
```python
QUALIFIED_STATUS = "✅ Aprobado - Respuesta enviada"
```
Use `Lead.status_filtrado == QUALIFIED_STATUS` in all queries. Never compare partial strings.

**Warning signs:** `calificados` count returns 0 despite approved leads existing in DB.

### Pitfall 4: Fecha_Recepcion Format Variants

**What goes wrong:** `datetime.fromisoformat("2026-03-30T17:45:02.000Z")` raises `ValueError` in Python < 3.11 (the `Z` suffix is not valid ISO 8601 for `fromisoformat` until 3.11).

**Why it happens:** Live data contains both `"...Z"` and `"...+00:00"` variants. The project runs Python 3.12 in production but `fromisoformat` with `Z` only works in 3.11+.

**How to avoid:** Since the project targets Python 3.12, `datetime.fromisoformat(value.replace("Z", "+00:00"))` is safe, but is also unnecessary in 3.11+ where `fromisoformat` handles `Z` natively. Use:
```python
from datetime import datetime, timezone
def _parse_fecha(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
```

**Warning signs:** `ValueError: Invalid isoformat string` in sync logs.

### Pitfall 5: Bloqueado Empty String vs "FALSE"

**What goes wrong:** Treating `""` (empty) as True/unknown and `"FALSE"` as False, creating a tri-state where none actually exists.

**Why it happens:** Sheet has 393 rows with empty Bloqueado (blocked status rows) and 337 rows with "FALSE" (non-blocked rows). The blocked rows have empty Bloqueado because the automation doesn't write "TRUE" for blocked senders — it relies on `Status_Filtrado = "🚫 Remitente bloqueado"` as the authority.

**How to avoid:** `bloqueado = (raw == "TRUE")` is sufficient. Both `""` and `"FALSE"` map to `False`. The authoritative "is this blocked?" signal is `status_filtrado`, not `bloqueado`.

### Pitfall 6: SyncLog source Collision with Pipedrive

**What goes wrong:** Sheets sync writes `SyncLog(source="pipedrive")` — the existing concurrency guard in `sync_pipedrive` then sees a "running" Sheets log and no-ops.

**Why it happens:** Copy-paste of the sync_pipedrive boilerplate without changing the `source` field.

**How to avoid:** `sync_sheets` must use `SyncLog(source="sheets")`. The concurrency guard in each function should filter by its own source: `.filter(SyncLog.source == "sheets", SyncLog.status == "running")`.

---

## Runtime State Inventory

This is a greenfield integration (new `leads` table, new `sheets.py`). No rename/refactor in scope.

**None — no runtime state to migrate. Alembic migration creates the `leads` table from scratch.**

---

## Environment Availability

| Dependency | Required By | Available | Value | Fallback |
|------------|------------|-----------|-------|----------|
| `GOOGLE_SHEETS_ID` | `sheets.py` | ✓ | `1LKdDo7IqMCpBg7nNVVCeNyjrHjPXxmkdt9Oa5zTwais` | — |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | `sheets.py` | ✓ | Service account `seg-dashboard@fleet-furnace-440814-b7.iam.gserviceaccount.com` | — |
| gspread library | `sheets.py` | ✓ | Already in pyproject.toml | — |
| google-auth library | `sheets.py` | ✓ | Already in pyproject.toml | — |
| Google Sheets API network access | `sheets.py` (sync) | ✓ | Verified: 730 rows fetched, 0.40s latency | — |
| Python 3.12 | `datetime.fromisoformat` with Z | ✓ | .python-version = 3.12 | — |

**Missing dependencies with no fallback:** none

**Note for tests:** `sync_sheets` tests must mock the gspread client (same pattern as `mock_pipedrive_transport` in conftest.py). Do not make live Sheet calls in the test suite — use a `mock_sheets_rows` fixture with a representative sample of the 3 status values.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | none (pytest discovers tests/) |
| Quick run command | `uv run pytest tests/test_leads.py -x -q` |
| Full suite command | `uv run pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SHEET-01 | `sync_sheets()` upserts rows by sheet_row_id | unit | `pytest tests/test_leads.py::test_sync_sheets_upsert -x` | No — Wave 0 |
| SHEET-01 | `sync_sheets()` is idempotent (2nd sync = 0 new rows) | unit | `pytest tests/test_leads.py::test_sync_sheets_idempotent -x` | No — Wave 0 |
| SHEET-01 | `sync_sheets()` writes SyncLog(source="sheets") | unit | `pytest tests/test_leads.py::test_sync_sheets_log -x` | No — Wave 0 |
| SHEET-01 | Padding handles short rows without IndexError | unit | `pytest tests/test_leads.py::test_get_leads_rows_padding -x` | No — Wave 0 |
| SHEET-02 | Exact talent name match resolves talent_id | unit | `pytest tests/test_leads.py::test_resolve_talent_id_exact -x` | No — Wave 0 |
| SHEET-02 | Unknown talent name → talent_id=None | unit | `pytest tests/test_leads.py::test_resolve_talent_id_unknown -x` | No — Wave 0 |
| SHEET-02 | `"✅ Aprobado - Respuesta enviada"` counts as Calificado | unit | `pytest tests/test_leads.py::test_calificado_count -x` | No — Wave 0 |
| SHEET-02 | `score_calidad` empty string → None (no crash) | unit | `pytest tests/test_leads.py::test_score_parsing -x` | No — Wave 0 |
| DASH-04 | `GET /leads` returns 200 with auth | integration | `pytest tests/test_leads.py::test_leads_endpoint_auth -x` | No — Wave 0 |
| DASH-04 | `GET /leads` returns 401 without auth | integration | `pytest tests/test_leads.py::test_leads_endpoint_unauth -x` | No — Wave 0 |
| DASH-04 | `GET /leads/summary` returns totals and calificados | integration | `pytest tests/test_leads.py::test_leads_summary_endpoint -x` | No — Wave 0 |
| DASH-01 | `GET /dashboard/summary` includes leads_totales + calificados | integration | `pytest tests/test_leads.py::test_dashboard_summary_leads_kpis -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_leads.py -x -q`
- **Per wave merge:** `uv run pytest -x -q`
- **Phase gate:** Full suite green (currently 57 tests passing; Phase 3 adds ~12 more)

### Wave 0 Gaps

- [ ] `tests/test_leads.py` — covers all REQ IDs above
- [ ] `tests/conftest.py` — add `seed_leads` fixture and `mock_sheets_rows` fixture
- [ ] `app/schemas/leads.py` — LeadRow, LeadsSummary Pydantic models (needed before router tests)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (inherited) | JWT cookie via `get_current_user` dependency on all leads routes |
| V3 Session Management | yes (inherited) | Same cookie mechanism as existing routes |
| V4 Access Control | yes | `dependencies=[Depends(get_current_user)]` on router — same as dashboard |
| V5 Input Validation | yes | `SheetLeadRow` Pydantic model validates all Sheet-sourced data before DB write |
| V6 Cryptography | no | No new crypto; service account JSON handled by google-auth |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Service account JSON in logs | Information Disclosure | `error_message = str(exc)` only — never log gspread response objects (may contain credential reflections in error messages) |
| XSS via Sheet content (Asunto, Remitente_Nombre) | Tampering | Escape in Jinja2 / JS text nodes — same pattern as deal titles; never inject raw Sheet strings as innerHTML |
| Unauthorized leads read | Elevation of Privilege | Router-level `dependencies=[Depends(get_current_user)]` |
| Sheet mutation (CRITICAL CONSTRAINT) | Tampering | gspread client used read-only (`get_all_values`, `open_by_key`); no `update`, `append_row`, or write methods called anywhere |

**CLAUDE.md critical constraint verified:** This phase is read-only from Google Sheets. The `sheets.py` integration only uses `ws.get_all_values()` — no write operations.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `oauth2client` for gspread auth | `google-auth` + `Credentials.from_service_account_info` | gspread 6.x dropped oauth2client — use google-auth pattern only |
| `gspread.service_account()` with file path | `gspread.authorize(Credentials.from_service_account_info(dict))` | Env var JSON string → dict → Credentials; no file on disk needed |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Sheet row number is stable (append-only, no inserts/reorders) | Natural Key Strategy | Rows shift → all subsequent rows get wrong data on next sync; recoverable by truncating leads table and re-syncing |
| A2 | `Talento_Mencionado` values will remain exact-string matches to DB names as new talents are added | Talent Match | New talents with variant names would fall into "Sin talento asignado" bucket silently |
| A3 | The 3 Status_Filtrado values are exhaustive and will not change | Calificado Definition | A new 4th status would need mapping in `STATUS_DISPLAY` and a planner decision on whether it counts as Calificado |
| A4 | `Convertido_a_Prospecto` being empty for all 730 rows is current state, not permanent | Column Analysis | When populated in future, existing model stores it correctly (bool field, already handled) |

---

## Open Questions

1. **Should `sync_sheets` run in the same scheduler job as `sync_pipedrive`, or as a separate APScheduler job?**
   - What we know: Both are hourly; the existing scheduler has one job.
   - Recommendation: Same job, sequential execution. Total time: Pipedrive sync (~variable) + Sheets sync (~0.5s). If Pipedrive fails, Sheets sync is skipped — acceptable tradeoff for simplicity. Can be separated later if needed.

2. **Should the Leads tab show leads from all time or only the current month?**
   - What we know: Leads span 2026-03-30 to 2026-06-14. Mockup shows "este mes" in the per-talent bars title.
   - Recommendation: Default to all-time for the list; allow month filter for the per-talent bars (same month selector that exists in the nav bar). Planner decides.

3. **Should "Sin talento asignado" leads appear in the per-talent bars section?**
   - What we know: All 730 current rows have a talent — "Sin talento asignado" bucket is currently empty. It may become relevant if the Sheet adds rows without `Talento_Mencionado`.
   - Recommendation: Include a "Sin asignar" row at the bottom of the talent bars section, conditionally rendered if count > 0.

---

## Sources

### Primary (HIGH confidence)
- Live Google Sheet — `get_all_values()` on 730 rows, enumerated all distinct values for Status_Filtrado, Score_Calidad, Talento_Mencionado, Bloqueado, Convertido_a_Prospecto, ID_Lead, Threadid, Fecha_Recepcion format
- `app/models.py` — existing SQLAlchemy 2.0 model patterns
- `app/sync/jobs.py` — sync pattern to mirror (`sync_pipedrive`)
- `app/sync/scheduler.py` — APScheduler hook point
- `app/integrations/pipedrive.py` — integration module pattern to mirror
- `app/routers/dashboard.py` — router pattern and extension point
- `tests/conftest.py` — test fixture patterns to extend
- `app/config.py` — `GOOGLE_SHEETS_ID` and `GOOGLE_SERVICE_ACCOUNT_JSON` already in Settings

### Secondary (MEDIUM confidence)
- CONTEXT.md decisions D-29 through D-38 — locked decisions
- `.planning/reference/mockup.html` — `#page-leads` UI structure, CSS classes
- CLAUDE.md STACK.md section — gspread + google-auth version pins

### Tertiary
- None — all claims verified against live data or existing codebase.

---

## Metadata

**Confidence breakdown:**
- Live Sheet analysis: HIGH — verified by direct gspread connection against production Sheet
- Standard stack: HIGH — no new packages; all dependencies already in project
- Architecture: HIGH — mirrors established Pipedrive sync pattern exactly
- Natural key strategy: MEDIUM-HIGH — sheet row number is pragmatic; assumption A1 carries low but non-zero risk
- Pitfalls: HIGH — Pitfall 1 (ID_Lead empty) is a hard fact; others verified against live data patterns

**Research date:** 2026-06-14
**Valid until:** 2026-07-14 (Sheet structure unlikely to change; re-verify if new automation is deployed)

---

## RESEARCH COMPLETE
