# Phase 8: Pre-Junta Fixes — Pattern Map

**Mapped:** 2026-06-24
**Files analyzed:** 8 files to be modified
**Analogs found:** 8 / 8 (all files are modifications to existing code — all analogs are the files themselves)

---

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------|------|-----------|----------------|---------------|
| `app/sync/jobs.py` | sync-job | batch (Pipedrive→SQLite) | itself (lines 146-150 are the bug site) | exact |
| `app/services/kpis.py` | service | CRUD / transform | itself (`talent_detail()` lines 147-249 is the pattern for new `flujo_dinero_kpis()`) | exact |
| `app/schemas/dashboard.py` | schema | transform | itself (`TalentDetail` lines 112-124 shows how Optional Phase 4 fields were added) | exact |
| `app/routers/dashboard.py` | router | request-response | itself (`get_talent_detail()` lines 126-182 shows how service results are assembled into response) | exact |
| `frontend/index.html` | template | — | itself (lines 119-127 are the two insertion points) | exact |
| `frontend/js/dashboard.js` | frontend-module | event-driven | itself (`setCampaignFilter` / `_campaignFilter` pattern at lines 17-21, 811-824) | exact |
| `frontend/css/styles.css` | stylesheet | — | itself (`.filter-pill` pattern lines 1765-1798, `.kpi-t` variants lines 1424-1506) | exact |

---

## Pattern Assignments

### `app/sync/jobs.py` — FIX-01: lost_reason field mapping

**What changes:** Lines 80 and 146-150. Replace custom-field lookup with direct standard-field read.

**Bug site — lines 80 + 146-150 (current broken code):**
```python
# Line 80 — looks up "Razón de pérdida" as if it were a CUSTOM field:
loss_reason_key = key_by_name.get("Razón de pérdida")

# Lines 146-150 — uses that key, which is always None for a standard field:
loss_reason = (
    pipedrive.resolve_custom_field(deal, loss_reason_key, option_labels)
    if loss_reason_key
    else None
)
```

**Pattern for the fix — copy from how other standard top-level fields are read (lines 130-134):**
```python
# Standard field reads in the same loop — copy this pattern:
value = float(deal.get("value") or 0)        # line 130
stage_id = deal["stage_id"]                   # line 131
status = deal["status"]                       # line 133

# Apply same pattern to lost_reason:
loss_reason = deal.get("lost_reason") or None
# existing_deal.loss_reason = loss_reason   ← line 197, unchanged
```

**Line 197 (unchanged — already correct):**
```python
existing_deal.loss_reason = loss_reason
```

**Cleanup:** Line 80 (`loss_reason_key = key_by_name.get("Razón de pérdida")`) becomes dead code after the fix. Remove or comment it. The pattern for keeping/removing: `brand_category_key` (line 81) and `expected_collection_date_key` (line 82) show how custom fields are legitimately looked up — `loss_reason_key` should be removed since `lost_reason` is confirmed standard.

**Error handling pattern (lines 216-222) — unchanged, wraps the entire sync function:**
```python
except Exception as exc:  # noqa: BLE001 - persist error, never re-raise raw request/response
    db.rollback()
    sync_log.status = "error"
    sync_log.finished_at = datetime.now(timezone.utc)
    sync_log.error_message = str(exc)
    db.commit()
    db.refresh(sync_log)
```

---

### `app/services/kpis.py` — FIX-02: new `flujo_dinero_kpis()` function

**What changes:** Add a new function after `talent_detail()` (after line 249).

**Imports pattern (lines 1-17) — copy exactly, add TrelloCard import inside function body (same pattern as trello_service imports):**
```python
from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from app.models import Deal, Talent
from app.services.funnel import talent_funnel
```

**Core query pattern — copy from `talent_detail()` lines 174-183:**
```python
# Two-column aggregate query: (count, sum)
won_row = db.query(
    func.count(Deal.id),
    func.coalesce(func.sum(Deal.value), 0.0),
).filter(Deal.talent_id == talent_id, Deal.status == "won").one()
won_count, won_value = won_row[0], won_row[1] or 0.0
```

**KPI tile return shape — copy from `global_kpis()` lines 61-87 and `talent_detail()` lines 185-189:**
```python
kpis = [
    {"label": "Pipeline", "value": float(pipeline_row), "count": None, "variant": "accent"},
    {"label": "Cerrados", "value": float(won_value), "count": won_count, "variant": "purple"},
    {"label": "Comisión", "value": float(commission), "count": None, "variant": "green"},
]
```

**New function to write (full pattern from RESEARCH.md, uses codebase query style):**
```python
def flujo_dinero_kpis(db: Session, talent_id: int) -> dict:
    """Return Flujo de dinero KPIs: Campañas firmadas, Cobrado, Pendiente.

    NOTE: stage_name == "Contrato" not "Contrato y factura" — normalized
    by sync/jobs.py _STAGE_CANONICAL at line 92.
    """
    from app.models import TrelloCard  # local import to mirror existing service pattern

    # Campañas firmadas: deals in "Contrato" stage (won OR open)
    contrato_row = db.query(
        func.count(Deal.id),
        func.coalesce(func.sum(Deal.value), 0.0),
    ).filter(
        Deal.talent_id == talent_id,
        Deal.stage_name == "Contrato",
        Deal.status.in_(["won", "open"]),
    ).one()
    firmadas_count, firmadas_value = contrato_row[0], contrato_row[1] or 0.0

    # Cobrado: deals with a TrelloCard in list_state="cerrado"
    cobrado_value = db.query(
        func.coalesce(func.sum(Deal.value), 0.0),
    ).join(TrelloCard, TrelloCard.deal_id == Deal.id).filter(
        Deal.talent_id == talent_id,
        TrelloCard.list_state == "cerrado",
    ).scalar() or 0.0

    pendiente = max(0.0, firmadas_value - cobrado_value)

    return {
        "kpis": [
            {"label": "Campañas firmadas", "value": float(firmadas_value),
             "count": firmadas_count, "variant": "blue"},
            {"label": "Cobrado",           "value": float(cobrado_value),
             "count": None,                "variant": "green"},
            {"label": "Pendiente por cobrar", "value": float(pendiente),
             "count": None,                   "variant": "amber"},
        ]
    }
```

---

### `app/schemas/dashboard.py` — FIX-02: add `flujo_dinero` field to `TalentDetail`

**What changes:** Add one Optional field to `TalentDetail` (lines 112-124).

**Pattern for adding Optional fields — copy from how Phase 4 added income_projection (lines 121-124):**
```python
class TalentDetail(BaseModel):
    talent_id: int
    name: str
    category: str | None = None
    kpis: list[KpiTile]
    funnel: list[StageBucket]
    lost_summary: list[LostReasonSummary]
    lost_opportunities: list[LostOpportunity]
    brand_categories: list[BrandCategorySlice]
    # Phase 4 additions — Optional so existing tests without Trello data remain unbroken
    income_projection: list[MonthProjection] | None = None
    payment_calendar: list[CalendarEntry] | None = None
    deals: list[DealRow] | None = None
    # Phase 8 addition — Optional to avoid breaking existing tests
    flujo_dinero: list[KpiTile] | None = None
```

**Critical:** `flujo_dinero` carries the same `list[KpiTile]` type as `kpis` — `KpiTile` is already defined at line 11 and imported. No new Pydantic model needed.

---

### `app/routers/dashboard.py` — FIX-02: populate `flujo_dinero` in `get_talent_detail()`

**What changes:** Add ~4 lines to `get_talent_detail()` (lines 126-182).

**Import pattern (lines 11-36) — add `kpi_service.flujo_dinero_kpis` call; no new imports needed:**
```python
from app.services import kpis as kpi_service   # already imported at line 33
```

**Pattern for calling a new service function and building typed list — copy from lines 162-168:**
```python
# Phase 4 — DASH-02: income projection, payment calendar, individual deals
proj_dicts = trello_service.income_projection(db, talent_id)
cal_dicts = trello_service.payment_calendar(db, talent_id)
deal_dicts = trello_service.deals_for_talent(db, talent_id)

income_proj = [MonthProjection(**p) for p in proj_dicts] if proj_dicts else None
payment_cal = [CalendarEntry(**c) for c in cal_dicts] if cal_dicts else None
deals = [DealRow(**d) for d in deal_dicts] if deal_dicts else None
```

**New lines to add (after line 168, before `return TalentDetail(...)`):**
```python
# Phase 8 — FIX-02: Flujo de dinero KPI tiles
flujo_data = kpi_service.flujo_dinero_kpis(db, talent_id)
flujo_dinero_tiles = [KpiTile(**k) for k in flujo_data["kpis"]]
```

**Pattern for adding field to TalentDetail constructor — copy from lines 170-182:**
```python
return TalentDetail(
    talent_id=detail["talent_id"],
    name=detail["name"],
    category=detail["category"],
    kpis=kpi_tiles,
    funnel=funnel_stages,
    lost_summary=lost_summary,
    lost_opportunities=lost_opps,
    brand_categories=brand_cats,
    income_projection=income_proj,
    payment_calendar=payment_cal,
    deals=deals,
    flujo_dinero=flujo_dinero_tiles,   # ADD THIS LINE
)
```

**Error handling pattern (lines 143-152) — unchanged, wraps `kpi_service.talent_detail()` only:**
```python
try:
    detail = kpi_service.talent_detail(db, talent_id)
except ValueError:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Talent not found",
    )
```

---

### `frontend/index.html` — FIX-02 + FIX-03 + FIX-04

**What changes:** Three text/HTML edits.

**FIX-04 — Rename chart title (line 126):**
```html
<!-- BEFORE (line 126): -->
<div class="section-title">Proyección de ingresos por mes</div>

<!-- AFTER: -->
<div class="section-title">Histórico de ingresos por mes</div>
```

**FIX-02 — Insert KPI toggle above `#talent-kpis` (lines 119-122):**
```html
<!-- BEFORE (lines 119-122): -->
<!-- (3) KPI row: 3 horizontal tiles -->
<div class="section">
  <div class="kpi-row-3" id="talent-kpis"></div>
</div>

<!-- AFTER: -->
<!-- (3) KPI toggle + KPI row -->
<div class="section">
  <div class="kpi-toggle" id="kpi-toggle">
    <button class="kpi-toggle-btn active" onclick="setKpiView('flujo')" data-view="flujo">Flujo de dinero</button>
    <button class="kpi-toggle-btn" onclick="setKpiView('operativa')" data-view="operativa">Operativa</button>
  </div>
  <div class="kpi-row-3" id="talent-kpis"></div>
</div>
```

**Cache-busting — bump version param (line 8):**
```html
<!-- BEFORE: -->
<link rel="stylesheet" href="/css/styles.css?v=20260622b">

<!-- AFTER: -->
<link rel="stylesheet" href="/css/styles.css?v=20260625a">
```

---

### `frontend/js/dashboard.js` — FIX-02 + FIX-03 + FIX-04

**What changes:** 4 distinct edits across the file.

**FIX-02 — Toggle state variable (copy module-level pattern from lines 17-21):**
```javascript
// Module-level state — copy exact pattern of _campaignFilter:
// Campaign filter state (module-level so setCampaignFilter can re-render without re-fetching)
let _campaignDeals = null;
let _campaignLostOpps = null;
let _campaignFilter = 'all';

// Add alongside these at the top of the file:
let _kpiView = 'flujo';         // 'flujo' | 'operativa'
let _talentDetailData = null;   // cache the last loaded talent detail response
```

**FIX-02 — Toggle handler (copy `setCampaignFilter` pattern from lines 811-824):**
```javascript
// setCampaignFilter pattern (lines 811-824) — copy structure:
function setCampaignFilter(key) {
  _campaignFilter = key;
  const pillsEl = document.getElementById('campaign-filter-pills');
  if (pillsEl) {
    pillsEl.querySelectorAll('.filter-pill').forEach((p) => {
      const isActive = p.dataset.filter === key;
      const f = CAMPAIGN_FILTERS.find((cf) => cf.key === p.dataset.filter);
      p.className = isActive
        ? `filter-pill active ${f ? f.cls : ''}`.trimEnd()
        : 'filter-pill';
    });
  }
  renderCampaignRows();
}

// New function — same shape:
function setKpiView(view) {
  _kpiView = view;
  const toggleEl = document.getElementById('kpi-toggle');
  if (toggleEl) {
    toggleEl.querySelectorAll('.kpi-toggle-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.view === view);
    });
  }
  if (!_talentDetailData) return;
  if (view === 'flujo') {
    renderKpisInto(_talentDetailData.flujo_dinero || [], 'talent-kpis');
  } else {
    renderKpisInto(_talentDetailData.kpis, 'talent-kpis');
  }
}
```

**FIX-02 — Update `loadTalentDetail()` to cache data and default to flujo view (lines 1196-1234):**
```javascript
// Current line 1206-1214:
const data = await res.json();
// ...
renderKpisInto(data.kpis, "talent-kpis");

// Replace with:
const data = await res.json();
_talentDetailData = data;   // cache for toggle re-render
_kpiView = 'flujo';         // always default to flujo on new talent load

// Reset toggle button state:
const toggleEl = document.getElementById('kpi-toggle');
if (toggleEl) {
  toggleEl.querySelectorAll('.kpi-toggle-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.view === 'flujo');
  });
}

// Render flujo by default (was: renderKpisInto(data.kpis, "talent-kpis")):
renderKpisInto(data.flujo_dinero || data.kpis, 'talent-kpis');
```

**FIX-03 — Add Trello badge in `renderFunnel()` (lines 408-423):**
```javascript
// BEFORE (line 416):
return `
  <div class="funnel-row">
    <span class="f-label">${escHtml(stage.stage)}</span>
    ...
  </div>
`;

// AFTER — add badge for Trello-sourced stages:
const TRELLO_STAGES = ["En ejecución", "Cobranza"];
// (define TRELLO_STAGES once at module level, near FUNNEL_COLORS)

// In the template (line 416):
const trelloBadge = TRELLO_STAGES.includes(stage.stage)
  ? `<span class="trello-src-badge">vía Trello</span>`
  : "";
return `
  <div class="funnel-row">
    <span class="f-label">${escHtml(stage.stage)}${trelloBadge}</span>
    ...
  </div>
`;
```

**FIX-03 — Same badge in `renderTalentFunnel()` (lines 626-634):**
```javascript
// BEFORE (line 628):
<span class="f-label">${escHtml(stage.stage)}</span>

// AFTER (reuse same TRELLO_STAGES constant defined once at module level):
const trelloBadge = TRELLO_STAGES.includes(stage.stage)
  ? `<span class="trello-src-badge">vía Trello</span>`
  : "";
// In template:
<span class="f-label">${escHtml(stage.stage)}${trelloBadge}</span>
```

**FIX-04 — Rename legend label in `renderIncomeProjection()` (lines 974-978):**
```javascript
// BEFORE (line 976):
<div class="proj-legend-item"><div class="proj-legend-dot" style="background:var(--blue)"></div>Firmado (Proyección)</div>

// AFTER:
<div class="proj-legend-item"><div class="proj-legend-dot" style="background:var(--blue)"></div>En campaña</div>
```

**FIX-04 — Also rename sublabel in bar rendering (line 955):**
```javascript
// BEFORE (line 955):
const sublabel  = isCurrent ? "(Real)" : "(Proyección)";

// AFTER:
const sublabel  = isCurrent ? "(Real)" : "(Estimado)";
```

**XSS safety pattern — any new API-sourced string in innerHTML must use escHtml() (lines 55-60):**
```javascript
function escHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    // (continues with quote escaping)
}
```

---

### `frontend/css/styles.css` — FIX-02 + FIX-03

**What changes:** Append two new CSS blocks at the end of the file.

**FIX-02 — `.kpi-toggle` segmented control (new CSS, append after last rule ~line 1897):**

Copy the structural pattern from `.filter-pills` / `.filter-pill` (lines 1756-1798):
```css
/* ================================================================
   Phase 8 — KPI toggle segmented control (FIX-02)
   ================================================================ */

.kpi-toggle {
  display: flex;
  gap: 4px;
  padding: 4px;
  background: var(--bg4);
  border: 1px solid var(--border);
  border-radius: var(--r);
  margin-bottom: 12px;
}

.kpi-toggle-btn {
  flex: 1;
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 500;
  font-family: 'DM Sans', sans-serif;
  border-radius: 7px;
  border: none;
  background: transparent;
  color: var(--text2);
  cursor: pointer;
  transition: all 0.15s;
}

.kpi-toggle-btn:hover { color: var(--text); }

.kpi-toggle-btn.active {
  background: var(--bg2);
  border: 1px solid var(--borderM);
  color: var(--text);
}
```

**Reference: variable names used** — all from existing CSS variables; confirmed in `.filter-pill` (lines 1773-1789): `--bg4`, `--border`, `--r`, `--bg2`, `--borderM`, `--text`, `--text2`.

**FIX-03 — `.trello-src-badge` inline label (new CSS, append after `.kpi-toggle` block):**

Copy the visual style pattern from `.sbadge` (existing status badge pattern — e.g., `.sbadge.ejecucion` used in campaign table rows):
```css
/* Phase 8 — Trello source badge on funnel stage labels (FIX-03) */

.trello-src-badge {
  display: inline-block;
  font-size: 9px;
  font-weight: 700;
  font-family: 'Sora', sans-serif;
  letter-spacing: 0.3px;
  text-transform: uppercase;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(14, 165, 176, 0.12);
  border: 1px solid rgba(14, 165, 176, 0.3);
  color: #40d4de;
  margin-left: 5px;
  vertical-align: middle;
  line-height: 1.4;
}
```

**Reference for Trello color values** — from existing `.filter-pill.active.ejecucion` (line 1795): `background: rgba(14,165,176,0.12); border-color: #0ea5b0; color: #40d4de;`. The badge reuses these exact values since "En ejecución" and "Cobranza" are the Trello-sourced stages.

---

## Shared Patterns

### XSS Safety (applies to all new innerHTML insertions)
**Source:** `frontend/js/dashboard.js` lines 55-60
**Apply to:** Every new string interpolated into innerHTML in `setKpiView()`, `renderFlujoDineroKpis()` if extracted, and the Trello badge conditional (though badge text is a literal, not API-sourced — safe).
```javascript
// All API-sourced strings must go through escHtml():
escHtml(stage.stage)        // stage name from API
escHtml(tile.label)         // KPI label from API (already done in renderKpisInto line 577)
```

### DB Session Pattern (applies to new service function)
**Source:** `app/services/kpis.py` lines 1-17, `app/routers/dashboard.py` lines 11-42
**Apply to:** `flujo_dinero_kpis(db, talent_id)` — `db: Session` is first param, never imported from database directly in service layer. Session is always injected via router's `Depends(get_db)`.

### Module-Level State for Re-Render Without Re-Fetch (applies to KPI toggle)
**Source:** `frontend/js/dashboard.js` lines 17-21
**Apply to:** `_kpiView` and `_talentDetailData` — same `let _variable = defaultValue` pattern as `_campaignFilter = 'all'`.

### SQLAlchemy Coalesce Guard (applies to new queries)
**Source:** `app/services/kpis.py` lines 29-31, 44-47
**Apply to:** All `func.sum()` calls in `flujo_dinero_kpis()` — always wrap with `func.coalesce(..., 0.0)` and add `or 0.0` after `.scalar()` / `.one()` to guard against NULL when no rows match.
```python
func.coalesce(func.sum(Deal.value), 0.0)
# and after .scalar():
cobrado_value = db.query(...).scalar() or 0.0
```

### Optional Schema Field Addition (applies to TalentDetail)
**Source:** `app/schemas/dashboard.py` lines 121-124
**Apply to:** `flujo_dinero` field — must be `list[KpiTile] | None = None` (not bare `list`) to avoid breaking existing tests that construct `TalentDetail` without this field.

### CSS Version Cache-Busting (applies to any CSS change)
**Source:** `frontend/index.html` line 8
**Apply to:** Bump `?v=20260622b` → `?v=20260625a` when adding new CSS rules.
```html
<link rel="stylesheet" href="/css/styles.css?v=20260625a">
```

---

## No Analog Found

All 8 files in scope have direct existing analogs — they are modifications to existing files, not new files. The only truly new code constructs are:

| Construct | Where It Goes | Why No Analog | Pattern to Use Instead |
|-----------|---------------|---------------|------------------------|
| `.kpi-toggle` segmented control CSS | `styles.css` (append) | First segmented control in codebase | Use `.filter-pill` / `.filter-pills` pattern (lines 1756-1798) — closest existing component |
| `.trello-src-badge` CSS | `styles.css` (append) | First source-attribution badge in codebase | Use `.filter-pill.active.ejecucion` color values (line 1795) for the teal Trello color |
| `TRELLO_STAGES` constant | `dashboard.js` (module level) | First domain-constant array beyond filter config | Use `CAMPAIGN_FILTERS` array (lines 22-32) as structural pattern |

---

## Pitfall Register (for planner to include as pre-conditions)

| Pitfall | File | Guard |
|---------|------|-------|
| Incremental sync won't backfill old lost deals after FIX-01 | `app/sync/jobs.py` | Wave task: force full re-sync after deploy by nullifying last SyncLog or truncating `updated_since` |
| `Deal.stage_name == "Contrato y factura"` returns 0 results | `app/services/kpis.py` | Use `"Contrato"` (normalized by `_STAGE_CANONICAL` in jobs.py line 92) |
| `TalentDetail` constructor raises 422 if `flujo_dinero` field missing from schema | `app/schemas/dashboard.py` | Add schema field BEFORE modifying router |
| CSS changes invisible after deploy | `frontend/index.html` | Bump `?v=` cache-busting param on line 8 |
| `_talentDetailData` is `null` if toggle clicked before first talent loads | `dashboard.js` | Guard: `if (!_talentDetailData) return;` in `setKpiView()` |
| `TRELLO_AUTO_CREATE_ENABLED = False` must not be changed | `app/sync/jobs.py` line 37 | CRITICAL: do not touch this flag under any circumstances (CLAUDE.md) |

---

## Metadata

**Analog search scope:** All files listed in CONTEXT.md canonical_refs section
**Files scanned:** 8 source files read directly
**Pattern extraction date:** 2026-06-24
