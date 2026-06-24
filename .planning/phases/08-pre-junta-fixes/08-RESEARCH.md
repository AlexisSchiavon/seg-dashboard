# Phase 8: Pre-Junta Fixes — Research

**Researched:** 2026-06-24
**Domain:** Bug fixes + frontend KPI toggle + label/honesty corrections (existing Python/FastAPI/Vanilla JS stack)
**Confidence:** HIGH — all findings verified directly from source files, no external lookups required

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 (FIX-01):** Diagnose across three layers: `app/models.py`, `app/sync/jobs.py`, `app/services/kpis.py`. Fix at root cause.
- **D-02 (FIX-02):** Add segmented control above KPI cards in Por Talento. Two views: "Flujo de dinero" (default) / "Operativa" (current). Colors per PDF: azul / verde / naranja.
- **D-03 (FIX-03):** Add "(vía Trello)" label/badge to "En ejecución" and "Cobranza" funnel stages to distinguish Trello-sourced data.
- **D-04 (FIX-03):** Rename "Proyección de ingresos por mes" → "Histórico de ingresos por mes". Show only real historical data.
- **D-05 (Wave 4 optional):** Improve "Sin talento asignado" card visibility + verify APScheduler. Only if Waves 1–3 complete.

### Claude's Discretion

- Exact UI component style for the segmented control (tabs, pill buttons, etc.) — use existing CSS patterns, dark mode consistent
- Whether to add a tooltip or a static "(vía Trello)" text label on funnel stages — whichever is simpler with vanilla JS
- Whether `lost_reason` fix is in models.py column rename, sync mapping, or service function — diagnose first

### Deferred Ideas (OUT OF SCOPE)

- "Categorías de marca" section — field doesn't exist in Pipedrive. Topic for Luis meeting.
- Future revenue projection (stacked bar: Cobrado/Proyección/Pendiente) — "Fecha de cobro" doesn't exist.
- Webhook-based real-time sync (FUT-01) — deferred to v2.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FIX-01 | Lost reason bug: "Oportunidades perdidas" donut shows "Sin razón — 100%" | Root cause identified: `lost_reason` is a Pipedrive **standard field** but the sync reads it as if it were a custom field — see FIX-01 diagnosis below |
| FIX-02 | KPI toggle in Por Talento: segmented control "Flujo de dinero" / "Operativa" | HTML insertion point: `#talent-kpis` section (line 121 index.html); backend data already available via TrelloCard table |
| FIX-03 | Honesty fixes: funnel Trello labels + revenue chart rename | Funnel renders in `renderTalentFunnel()` and global `renderFunnel()`; chart title in HTML line 126; section title at line 127 |
| FIX-04 | Optional: "Sin talento asignado" card + APScheduler verification | Low priority, only if time permits |
</phase_requirements>

---

## Summary

This is a pure correction phase — no new dependencies, no new DB migrations required (with one exception: the `local_won_date` field for the revenue chart requires either adding a column or using the existing `add_time` field, see FIX-03 diagnosis). The three fixes operate across four layers: the Pipedrive sync mapping, the backend service, the frontend HTML structure, and the frontend rendering functions in `dashboard.js`.

**The most critical finding:** The `lost_reason` bug is NOT a column rename issue. The column in `models.py` is `loss_reason` (correct, consistent throughout backend). The bug is that Pipedrive's `lost_reason` is a **standard deal field** delivered at the top level of the deal JSON (`deal["lost_reason"]`), but `sync/jobs.py` tries to resolve it as a **custom field** via `key_by_name.get("Razón de pérdida")` and `resolve_custom_field()`. If "Razón de pérdida" is not found in Pipedrive's `/dealFields` as a custom field (which it won't be, since it's a standard field), `loss_reason_key` is `None` and `existing_deal.loss_reason` is always set to `None`. Every lost deal therefore has `loss_reason = None`, which the service renders as "Sin razón — 100%".

**Primary recommendation:** Fix `sync/jobs.py` to read `deal.get("lost_reason")` directly from the standard deal dict (not via `resolve_custom_field`). The column name `loss_reason` and all service/router code are correct and need no changes.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| FIX-01: lost_reason population | Backend — sync layer (`app/sync/jobs.py`) | — | Bug is in how the Pipedrive API response is read during sync, not in the model or service |
| FIX-01: lost_reason display | Backend — service (`app/services/kpis.py`) | Frontend (`dashboard.js renderLostOpportunities`) | Service already correct; frontend rendering already correct — only sync is wrong |
| FIX-02: KPI toggle | Frontend — `dashboard.js` + `styles.css` | Backend — `app/services/kpis.py` (new query) | Segmented control is pure frontend; "Cobrado" KPI requires a new backend query on TrelloCard |
| FIX-03: Funnel labels | Frontend — `dashboard.js renderTalentFunnel()` and `renderFunnel()` | — | Stage label display is entirely in JS rendering functions |
| FIX-03: Chart rename | Frontend — `index.html` line 126–127 | — | Text change in the `section-title` div |
| FIX-03: Revenue chart data | Backend — `app/services/trello_service.py income_projection()` | Frontend `renderIncomeProjection()` | The projection data already exists; rename + simplification is straightforward |

---

## Standard Stack

No new packages. Phase uses the existing stack exclusively.

| Component | File | Current State |
|-----------|------|---------------|
| Backend ORM | `app/models.py` | SQLAlchemy 2.0, `Deal.loss_reason` column exists |
| Sync engine | `app/sync/jobs.py` | Pipedrive sync loop with custom-field resolver |
| KPI service | `app/services/kpis.py` | `talent_detail()` reads `deal.loss_reason` correctly |
| Trello service | `app/services/trello_service.py` | `income_projection()`, `deals_for_talent()` already populated |
| Router | `app/routers/dashboard.py` | `GET /dashboard/talents/{id}` endpoint |
| Frontend JS | `frontend/js/dashboard.js` | `loadTalentDetail()`, `renderLostOpportunities()`, `renderTalentFunnel()`, `renderIncomeProjection()` |
| HTML | `frontend/index.html` | Por Talento tab structure at lines 91–184 |
| CSS | `frontend/css/styles.css` | `.filter-pill`, `.kpi-t`, `.kpi-row-3` — reusable patterns |

---

## Package Legitimacy Audit

> No external packages are installed in this phase. Audit skipped.

---

## FIX-01: lost_reason Bug — Full Diagnosis

### Root Cause: Standard Field Treated as Custom Field

**Layer 1 — `app/models.py` line 60:**
```python
loss_reason: Mapped[str | None] = mapped_column(String, nullable=True)
```
Column name is `loss_reason`. This is CORRECT and consistent. No rename needed.

**Layer 2 — `app/sync/jobs.py` lines 80 + 146-148 + 197 — THE BUG:**
```python
# Line 80: looks up "Razón de pérdida" as a CUSTOM field name in dealFields
loss_reason_key = key_by_name.get("Razón de pérdida")

# Lines 146-148: only resolves if a custom field key was found
loss_reason = (
    pipedrive.resolve_custom_field(deal, loss_reason_key, option_labels)
    if loss_reason_key
    else None
)

# Line 197: writes the result (None when key not found)
existing_deal.loss_reason = loss_reason
```

**The actual Pipedrive API response for v2 deals** delivers `lost_reason` as a top-level standard field — it is NOT in `custom_fields`. Per the CONTEXT.md canonical refs: "lost_reason is a standard field, plain text, 5 options". Pipedrive's v2 `/dealFields` endpoint lists only custom fields; standard fields like `lost_reason` do not appear there.

Result: `key_by_name.get("Razón de pérdida")` returns `None` (or possibly finds nothing because the Pipedrive standard field name is `lost_reason` not `"Razón de pérdida"`). Either way, `loss_reason_key is None` → loss_reason is always `None`.

**Layer 3 — `app/services/kpis.py` lines 203-204:**
```python
reason = deal.loss_reason or "Sin razón"
reason_counts[reason] = reason_counts.get(reason, 0) + 1
```
This is CORRECT. When all deals have `loss_reason = None`, all fall back to `"Sin razón"`, producing the "Sin razón — 100%" display. No fix needed here.

**Layer 4 — `app/integrations/pipedrive.py` `resolve_custom_field()` lines 83-96:**
Designed for custom fields in `deal["custom_fields"]`. Standard fields are at `deal["lost_reason"]` directly. This function should not be used for `lost_reason`.

### The Fix (one line in `sync/jobs.py`)

Replace the custom-field lookup with a direct standard field read:

```python
# BEFORE (lines 146-149) — reads from custom_fields, always None:
loss_reason = (
    pipedrive.resolve_custom_field(deal, loss_reason_key, option_labels)
    if loss_reason_key
    else None
)

# AFTER — reads standard field directly:
loss_reason = deal.get("lost_reason") or None
```

The `loss_reason_key` lookup at line 80 becomes dead code and can be removed, or left as is (harmless). `existing_deal.loss_reason = loss_reason` at line 197 requires no change.

**Post-fix action:** After deploying, trigger a full re-sync ("Sincronizar ahora") to backfill `loss_reason` for all existing deals. Because the sync is incremental by default, to force a full re-sync one must either: (a) clear the last successful SyncLog so `updated_since` is None, or (b) use the "Sincronizar ahora" button which calls the sync with whatever `updated_since` the last success provides. Check if existing lost deals will be re-fetched — if incremental sync only fetches deals updated since last sync, old lost deals may not be re-fetched. A one-time full sync (delete/nullify last successful SyncLog) may be needed.

---

## FIX-02: KPI Toggle in Por Talento — Full Diagnosis

### HTML Structure (index.html lines 119-122)

The current KPI section in Por Talento:
```html
<!-- (3) KPI row: 3 horizontal tiles -->
<div class="section">
  <div class="kpi-row-3" id="talent-kpis"></div>
</div>
```

The segmented control must be inserted ABOVE `#talent-kpis` inside this same `<div class="section">`.

### JavaScript Flow

`loadTalentDetail(talentId)` (line 1196 dashboard.js) calls `GET /dashboard/talents/{id}` and then:
- Line 1214: `renderKpisInto(data.kpis, "talent-kpis")` — renders the 3 "Operativa" KPI cards

The toggle must:
1. Insert a segmented control above `#talent-kpis`
2. On "Operativa" (current tab): call `renderKpisInto(data.kpis, "talent-kpis")` (unchanged)
3. On "Flujo de dinero" (new default): call a new `renderFlujoDineroKpis(flujoDineroData, "talent-kpis")`

### Backend: "Flujo de dinero" Data

The three KPIs required per D-02:

**Campañas firmadas** (azul): count + SUM(value) of deals where stage_name == "Contrato" AND (status == "won" OR status == "open") for this talent.
- Data source: `Deal` table, already in DB.
- Note: CONTEXT.md says stage "Contrato y factura" — but `sync/jobs.py` line 92 normalizes this to "Contrato" via `_STAGE_CANONICAL`. Use `"Contrato"` in the query.

**Cobrado** (verde): SUM of deal.value for TrelloCards with `list_state = "cerrado"` linked to this talent's deals.
- Data source: `TrelloCard` table joined to `Deal`, already available. `trello_service.deals_for_talent()` already returns rows with `list_state`. The value for `list_state == "cerrado"` can be summed from the existing data.

**Pendiente por cobrar** (naranja): arithmetic = Campañas firmadas total − Cobrado.
- No new query needed.

**New service function needed:** `flujo_dinero_kpis(db, talent_id) -> dict` in `app/services/kpis.py`.

**New response field:** `flujo_dinero` must be added to the `TalentDetail` Pydantic schema and the `get_talent_detail` router function.

### CSS: Segmented Control

No segmented control CSS exists yet. The `.filter-pill` pattern (styles.css line 1765) is the closest existing component — it uses pill buttons with `.active` state toggling. A segmented control can be built as a small horizontal container with two pill-style buttons using this existing pattern.

Recommended approach: new `.kpi-toggle` CSS class styled as a 2-button pill group. Uses existing CSS variables (`--bg4`, `--bg5`, `--border`, `--borderM`, `--text`, `--text2`).

### Colors per PDF

Per D-02:
- Campañas firmadas: azul → `var(--blue)` / `var(--blueD)` / `var(--blueT)` (matches `.kpi-t.blue`)
- Cobrado: verde → `var(--green)` / `var(--greenD)` / `var(--greenT)` (matches `.kpi-t.green`)
- Pendiente: naranja → `var(--amber)` / `var(--amberD)` / `var(--amberT)` (matches `.kpi-t.amber`)

All three are existing CSS variant classes on `.kpi-t`.

---

## FIX-03: Honesty Fixes — Full Diagnosis

### Funnel Stage Labels (D-03)

**Where funnel stage names are rendered:**

1. **Global Funnel tab** — `renderFunnel()` in `dashboard.js` lines 397-424. Renders into `#funnel-rows`. Stage label: `escHtml(stage.stage)` (line 413). The stage name comes from the backend's `STAGES` list in `funnel.py`.

2. **Per-Talent funnel** — `renderTalentFunnel()` in `dashboard.js` lines 589-637. Renders into `#talent-funnel`. Stage label: `escHtml(stage.stage)` (line 628).

Both render raw stage names. The fix is to annotate "En ejecución" and "Cobranza" with a "(vía Trello)" badge at render time in JS. This is purely a frontend change — the backend STAGES constant does not change.

**Simplest approach:** In `renderFunnel()` and `renderTalentFunnel()`, modify the label generation to check if `stage.stage === "En ejecución" || stage.stage === "Cobranza"` and append a `<span class="trello-badge">vía Trello</span>`.

**Backend source of truth** (for planner's reference): `funnel.py` lines 19-26 defines:
```python
STAGES = ["Llamada", "Cotización", "Negociación", "Contrato", "En ejecución", "Cobranza"]
```
Stages 5 and 6 ("En ejecución", "Cobranza") have no Pipedrive data source. The `talent_funnel()` function (line 144) queries `Deal.stage_name` for open deals — these stages will always show 0 unless deals are literally in a Pipedrive stage named "En ejecución" or "Cobranza" (which they are not — confirmed: real Pipedrive stages are Llamada/6, Cotización/7, Negociación/8, Contrato y factura/9).

### Revenue Chart Rename (D-04)

**HTML location:** `index.html` line 126-127:
```html
<div class="section-title">Proyección de ingresos por mes</div>
```
Fix: rename to "Histórico de ingresos por mes".

**Frontend rendering:** `renderIncomeProjection()` in `dashboard.js` lines 930-979. Currently shows 3 segments: `cobrado` (green), `proyeccion` (blue, labeled "Firmado (Proyección)"), `pendiente` (amber). Per D-04, only show real historical data.

The backend `income_projection()` in `trello_service.py` returns `{cobrado, proyeccion, pendiente}` where:
- `cobrado` = list_state=="cerrado" → this is real data (already collected)
- `proyeccion` = list_state=="ejecucion" → in-progress campaigns (uncertain)
- `pendiente` = list_state=="cobranza" → being collected (uncertain)

Per D-04 decision: "Show only real historical data — Cobrado by local_won_date, Firmado by won_time." However, `local_won_date` and `won_time` are **not stored in the Deal model or synced by jobs.py**. The model has only `add_time` (deal creation date). No migration for a new date column is in scope for this phase.

**Practical resolution for D-04:** The simplest honesty fix that requires no new column or migration is:
- Rename the section title (HTML)
- Remove or gray-out the "Proyección" segment label (rename from "Firmado (Proyección)" to "En campaña" or similar honest label)
- Keep showing the existing 4-month window with the 3 segments (cobrado/ejecucion/cobranza) but rename segments to be accurate:
  - "Cobrado" (green) = already collected
  - "En campaña" (blue, was "Proyección") = campaigns running, not yet collected  
  - "En cobranza" (amber, was "Pendiente") = in collection process

The planner should confirm with Alexis whether "remove the projection segment and show only cobrado" OR "rename the segments to honest labels" is the right call. Both require only frontend changes. The CONTEXT.md says "Show only real historical data" — this implies removing the proyeccion/pendiente bars and showing only cobrado. If that's the intent, the chart becomes much simpler.

**Recommendation for planner:** Default to renaming segments to honest labels (3-segment chart stays, labels change). Only remove segments if Alexis confirms "historical only" means cobrado-only.

---

## Architecture Patterns

### System Architecture Diagram

```
Pipedrive API v2
   |
   | deal["lost_reason"]  ← standard field (top-level)
   v
app/sync/jobs.py (sync_pipedrive)
   | existing_deal.loss_reason = deal.get("lost_reason")  ← FIX HERE
   v
SQLite: deals.loss_reason (column exists, was always NULL)
   v
app/services/kpis.py talent_detail()
   | deal.loss_reason or "Sin razón"
   v
GET /dashboard/talents/{id}  → lost_summary, lost_opportunities
   v
dashboard.js renderLostOpportunities()
   v
#lost-summary (donut chart)
```

```
FIX-02: KPI Toggle Flow

GET /dashboard/talents/{id}  (new field: flujo_dinero)
   |
   |── data.kpis          → "Operativa" tab (unchanged)
   └── data.flujo_dinero  → "Flujo de dinero" tab (new)
         |
         ├── campanas_firmadas: count + sum(deals where stage=="Contrato")
         ├── cobrado:           sum(deals with TrelloCard list_state=="cerrado")
         └── pendiente:         campanas_firmadas.value - cobrado
   v
dashboard.js: new segmented control above #talent-kpis
   renderFlujoDineroKpis() OR renderKpisInto() with different data
```

### Files to Modify

| File | Change | Scope |
|------|--------|-------|
| `app/sync/jobs.py` | Line ~146: replace `resolve_custom_field()` call with `deal.get("lost_reason")` | 2-line change |
| `app/sync/jobs.py` | Line ~80: remove or ignore `loss_reason_key` lookup (cleanup) | 1-line removal |
| `app/services/kpis.py` | Add `flujo_dinero_kpis(db, talent_id)` function | New function, ~25 lines |
| `app/schemas/dashboard.py` | Add `flujo_dinero` field to `TalentDetail` schema | Check file first |
| `app/routers/dashboard.py` | Populate `flujo_dinero` in `get_talent_detail()` | ~5 lines |
| `frontend/index.html` | Line 126: rename section title; insert toggle control HTML | 2 locations |
| `frontend/js/dashboard.js` | Add toggle logic, `renderFlujoDineroKpis()`, update `renderTalentFunnel()` and `renderFunnel()` for Trello badges | 4 changes |
| `frontend/css/styles.css` | Add `.kpi-toggle` segmented control styles | ~20 lines new CSS |

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| KPI toggle state | Custom event system | Simple JS variable `let _kpiView = 'flujo'` + onclick handlers (same pattern as `_campaignFilter`) |
| Segmented control | Complex component | Adapt existing `.filter-pill` pattern — 2 buttons, shared container |
| "Cobrado" computation | New complex query | Reuse `deals_for_talent()` return value in service (already has `list_state` per row) |
| Lost reason display | New renderer | `renderLostOpportunities()` already correct — only the data changes |

---

## Common Pitfalls

### Pitfall 1: Incremental Sync Won't Backfill Lost Deals
**What goes wrong:** After fixing `sync/jobs.py`, the `updated_since` filter means only recently-changed deals are re-synced. Old lost deals (never touched since last sync) keep `loss_reason = NULL`.
**Why it happens:** `SyncLog` records the last successful sync time; the next sync only fetches deals updated after that.
**How to avoid:** After deploying the fix, perform a one-time full sync by either: (a) running `sync_pipedrive` with the last SyncLog's `finished_at` nullified/removed, or (b) using a direct SQL update with the API data. The planner must include a "trigger full re-sync" step as a wave task.
**Warning signs:** Donut still shows "Sin razón — 100%" after first sync post-fix.

### Pitfall 2: Pipedrive v2 `lost_reason` Field Name
**What goes wrong:** The API might deliver the field as `loss_reason` not `lost_reason` in the actual v2 response JSON.
**Why it happens:** Pipedrive's v2 API documentation uses `lost_reason`; v1 uses `lose_reson` (historical). The CONTEXT.md confirms `lost_reason` is the standard field name.
**How to avoid:** The fix should use `deal.get("lost_reason")`. After first sync, check a known-lost deal's `loss_reason` column in the DB. If still NULL, try `deal.get("lose_reason")` or inspect the raw Pipedrive response via a test endpoint.
**Warning signs:** loss_reason still NULL after fix and re-sync.

### Pitfall 3: TalentDetail Schema Missing `flujo_dinero`
**What goes wrong:** Adding the `flujo_dinero` field to the service return dict but forgetting to add it to the Pydantic `TalentDetail` schema causes a 422/500 on the endpoint.
**Why it happens:** `dashboard.py` builds a `TalentDetail(...)` with keyword args — an extra key not in the schema raises a Pydantic validation error.
**How to avoid:** Check `app/schemas/dashboard.py` before modifying the router. Add the field there first.
**Warning signs:** 422 validation error on `GET /dashboard/talents/{id}` after the change.

### Pitfall 4: CSS Version Caching
**What goes wrong:** Changes to `styles.css` not visible in browser after deploy.
**Why it happens:** `index.html` uses `?v=20260622b` cache-busting suffix on CSS/JS imports (line 8). New CSS changes need a new version string.
**How to avoid:** Bump the version query param in `index.html` lines 8, 433-439 when adding new CSS.
**Warning signs:** Toggle does not appear after deploy despite CSS being written.

### Pitfall 5: "Contrato" vs "Contrato y factura" Stage Name
**What goes wrong:** Querying `Deal.stage_name == "Contrato y factura"` for "Campañas firmadas" returns 0 results.
**Why it happens:** `sync/jobs.py` line 92 normalizes "Contrato y factura" → "Contrato" via `_STAGE_CANONICAL`. All deals in that Pipedrive stage are stored as `stage_name = "Contrato"` in SQLite.
**How to avoid:** The `flujo_dinero_kpis` query must use `Deal.stage_name == "Contrato"`.
**Warning signs:** "Campañas firmadas" shows 0 count/value when deals clearly exist in that stage.

---

## Code Examples

### FIX-01: Sync Fix (verified from source)

```python
# app/sync/jobs.py — replace lines 146-149
# Source: direct read of sync/jobs.py and CONTEXT.md confirmed Pipedrive standard field

# REMOVE the custom-field approach:
# loss_reason_key = key_by_name.get("Razón de pérdida")  ← remove line 80
# loss_reason = (
#     pipedrive.resolve_custom_field(deal, loss_reason_key, option_labels)
#     if loss_reason_key
#     else None
# )

# REPLACE WITH:
loss_reason = deal.get("lost_reason") or None
# existing_deal.loss_reason = loss_reason  ← line 197, unchanged
```

### FIX-02: New Service Function (pattern)

```python
# app/services/kpis.py — new function
def flujo_dinero_kpis(db: Session, talent_id: int) -> dict:
    """Return Flujo de dinero KPIs: Campañas firmadas, Cobrado, Pendiente."""
    from app.models import TrelloCard

    # Campañas firmadas: deals in "Contrato" stage (won OR open)
    contrato_row = db.query(
        func.count(Deal.id),
        func.coalesce(func.sum(Deal.value), 0.0),
    ).filter(
        Deal.talent_id == talent_id,
        Deal.stage_name == "Contrato",  # normalized name, NOT "Contrato y factura"
        Deal.status.in_(["won", "open"]),
    ).one()
    firmadas_count, firmadas_value = contrato_row[0], contrato_row[1] or 0.0

    # Cobrado: deals linked to TrelloCards with list_state="cerrado"
    cobrado_row = db.query(
        func.coalesce(func.sum(Deal.value), 0.0),
    ).join(TrelloCard, TrelloCard.deal_id == Deal.id).filter(
        Deal.talent_id == talent_id,
        TrelloCard.list_state == "cerrado",
    ).scalar() or 0.0

    # Pendiente: arithmetic (no new query)
    pendiente = max(0.0, firmadas_value - cobrado_row)

    return {
        "kpis": [
            {"label": "Campañas firmadas", "value": float(firmadas_value),
             "count": firmadas_count, "variant": "blue"},
            {"label": "Cobrado",           "value": float(cobrado_row),
             "count": None, "variant": "green"},
            {"label": "Pendiente por cobrar", "value": float(pendiente),
             "count": None, "variant": "amber"},
        ]
    }
```

### FIX-02: Segmented Control CSS (new, uses existing variables)

```css
/* styles.css — append to bottom */
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
  border-radius: 7px;
  border: none;
  background: transparent;
  color: var(--text2);
  cursor: pointer;
  transition: all 0.15s;
  font-family: 'DM Sans', sans-serif;
}
.kpi-toggle-btn:hover { color: var(--text); }
.kpi-toggle-btn.active {
  background: var(--bg2);
  border: 1px solid var(--borderM);
  color: var(--text);
}
```

### FIX-03: Trello badge in renderTalentFunnel (pattern)

```javascript
// dashboard.js — in renderTalentFunnel() and renderFunnel(), replace the label line:
// BEFORE:
// `<span class="f-label">${escHtml(stage.stage)}</span>`

// AFTER:
const trelloStages = ["En ejecución", "Cobranza"];
const trelloBadge = trelloStages.includes(stage.stage)
  ? `<span class="trello-src-badge">vía Trello</span>`
  : "";
// HTML:
`<span class="f-label">${escHtml(stage.stage)}${trelloBadge}</span>`
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pipedrive `lost_reason` via custom field resolver | Read as standard top-level field `deal.get("lost_reason")` | FIX-01 | Donut shows real data after re-sync |
| "Proyección de ingresos por mes" (misleading) | "Histórico de ingresos por mes" | FIX-03 | Honest labeling |
| Single "Operativa" KPI view | Two-tab view: "Flujo de dinero" + "Operativa" | FIX-02 | PDF-aligned |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Pipedrive v2 `/deals` response delivers `lost_reason` as a top-level standard field (not inside `custom_fields`) | FIX-01 diagnosis | If it's actually in `custom_fields` under a different key, the fix needs a different approach. Verify by adding a debug log or test endpoint after first re-sync. |
| A2 | "Campañas firmadas" should filter `stage_name == "Contrato"` (normalized) not `"Contrato y factura"` | FIX-02 service | Confirmed via `sync/jobs.py` `_STAGE_CANONICAL` at line 92. Risk: if stage normalization changes, query breaks. LOW risk. |
| A3 | D-04 "historical only" means rename + honest segment labels, not remove proyeccion/pendiente entirely | FIX-03 | If Alexis wants cobrado-only bars, the chart simplification is larger. Planner should add a 1-min confirmation step. |

---

## Open Questions (RESOLVED)

1. **Full re-sync for FIX-01**
   - What we know: Incremental sync won't backfill old lost deals automatically
   - What's unclear: Whether "Sincronizar ahora" in prod will fetch deals updated long ago, or only recently changed ones
   - Recommendation: Add a Wave 1 task to verify re-sync strategy. If needed, create a one-time script to force `updated_since = None` for the next sync run.
   - **RESOLVED:** 08-01 Task 3 is a human-verify checkpoint that confirms re-sync via the "Sincronizar ahora" button and checks the SQLite DB for populated `loss_reason` values. The plan instructs the executor to reset `sync_state.last_sync` if needed to force a full re-sync.

2. **D-04: "Show only historical" — scope of chart simplification**
   - What we know: CONTEXT.md says "Show only real historical data — Cobrado by local_won_date, Firmado by won_time"
   - What's unclear: Neither `local_won_date` nor `won_time` exist in the Deal model. The chart currently shows `cobrado/proyeccion/pendiente` from Trello list_state.
   - Recommendation: For the June 25 deadline, rename segments to honest labels (no schema changes). Ask Alexis during review whether a deeper simplification (cobrado-only) is wanted post-junta.
   - **RESOLVED:** 08-03 Task 2 implements the rename approach: "Proyección de ingresos por mes" → "Histórico de ingresos por mes" with segment relabeling ("En campaña" / "(Estimado)"). The `cobrado/proyeccion/pendiente` bars come from real Trello list_state data (not fabricated future amounts), so renaming to honest labels satisfies "no invented future projections." Post-junta cobrado-only simplification deferred to a follow-up phase.

3. **Schemas file**
   - What we know: `app/schemas/dashboard.py` must be modified for FIX-02 but was not read
   - What's unclear: Exact schema structure for `TalentDetail` and whether `flujo_dinero` field needs a new Pydantic model
   - Recommendation: Planner must include a task to read `app/schemas/dashboard.py` before modifying the router.
   - **RESOLVED:** Per PATTERNS.md line analysis, `flujo_dinero` is added as `flujo_dinero: list[KpiTile] | None = None` to the existing `TalentDetail` schema — no new Pydantic model needed. 08-02 Task 1 includes `app/schemas/dashboard.py` in `read_first` and adds the field before wiring the router.

---

## Environment Availability

Step 2.6: All changes are code/config only within the existing running application. No new external tools needed.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| SQLAlchemy 2.0 | FIX-02 new query | Already installed | 2.0.x | — |
| TrelloCard table | FIX-02 "Cobrado" | Already in DB (Phase 4) | — | — |
| FastAPI | All backend changes | Already installed | 0.136.x | — |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pyproject.toml` (check for `[tool.pytest]` section) |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FIX-01 | `sync_pipedrive` writes `loss_reason` from `deal["lost_reason"]` standard field | unit | `uv run pytest tests/test_sync.py -x -k lost_reason` | Check — may need new test |
| FIX-01 | `talent_detail()` returns real reasons in `lost_summary` when DB has `loss_reason` set | unit | `uv run pytest tests/test_kpis.py -x -k lost` | Check — may need fixture update |
| FIX-02 | `flujo_dinero_kpis()` returns 3 tiles with correct values | unit | `uv run pytest tests/test_kpis.py -x -k flujo` | ❌ Wave 0 |
| FIX-02 | `GET /dashboard/talents/{id}` response includes `flujo_dinero` field | integration | `uv run pytest tests/test_dashboard.py -x -k flujo` | ❌ Wave 0 |
| FIX-03 | Section title "Histórico de ingresos por mes" present in HTML | manual | Browser inspection | ✅ (after edit) |
| FIX-03 | Funnel renders "(vía Trello)" badge on En ejecución + Cobranza | manual | Browser inspection | N/A |

### Wave 0 Gaps

- [ ] `tests/test_kpis.py` — add `test_flujo_dinero_kpis()` fixture and assertion
- [ ] `tests/test_dashboard.py` — add assertion that `flujo_dinero` key exists in talent detail response

*(Existing test infrastructure covers FIX-01 regression if test fixtures include a deal with `lost_reason` set.)*

---

## Security Domain

No new security surface in this phase. All changes are:
- A data mapping fix in the sync layer (reads from same trusted source)
- A new read-only DB query (same authentication and authorization as existing talent detail endpoint)
- Frontend label/UI changes (no new user inputs, no new XSS surfaces)

The `TRELLO_AUTO_CREATE_ENABLED = False` flag in `sync/jobs.py` line 37 is NOT touched by any fix in this phase.

---

## Sources

### Primary (HIGH confidence — direct source file reads)
- `app/models.py` line 60 — confirmed `loss_reason` column name
- `app/sync/jobs.py` lines 80, 146-148, 197 — confirmed bug location
- `app/services/kpis.py` lines 151, 203-216 — confirmed service reads `deal.loss_reason` correctly
- `app/services/funnel.py` lines 19-26 — confirmed STAGES list and "En ejecución"/"Cobranza" are Trello-only
- `frontend/index.html` lines 119-127 — confirmed HTML insertion points for toggle and title rename
- `frontend/js/dashboard.js` lines 397-424 (renderFunnel), 589-637 (renderTalentFunnel), 930-979 (renderIncomeProjection), 1196-1234 (loadTalentDetail)
- `frontend/css/styles.css` lines 1424-1506 (`.kpi-t` pattern), 1765-1795 (`.filter-pill` pattern)
- `app/routers/dashboard.py` lines 126-182 — confirmed endpoint path `GET /dashboard/talents/{id}`
- `app/services/trello_service.py` lines 179-234 — confirmed TrelloCard data available for "Cobrado"
- `app/integrations/pipedrive.py` lines 67-96 — confirmed `resolve_custom_field` reads from `custom_fields` dict (standard fields not there)
- `.planning/phases/08-pre-junta-fixes/08-CONTEXT.md` — Pipedrive field reality, 5 valid `lost_reason` options

### Tertiary (LOW confidence — documented assumption)
- A1: `lost_reason` delivery as top-level field in Pipedrive v2 response — based on CONTEXT.md statement "standard field, plain text" and confirmed behavior of `resolve_custom_field` only reading `custom_fields`. Verify post-fix.

---

## Metadata

**Confidence breakdown:**
- FIX-01 root cause: HIGH — bug clearly visible at `sync/jobs.py` line 80 + 146; column and service are consistent
- FIX-02 HTML structure: HIGH — read directly from index.html
- FIX-02 backend data: HIGH — TrelloCard table exists, list_state values confirmed
- FIX-03 label locations: HIGH — read directly from dashboard.js function bodies
- A1 (Pipedrive field delivery): LOW — based on CONTEXT.md assertion, not direct API inspection

**Research date:** 2026-06-24
**Valid until:** 2026-06-25 (phase executes same day)
