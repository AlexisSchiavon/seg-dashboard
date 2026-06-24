# Phase 8: Pre-Junta Fixes — Context

**Gathered:** 2026-06-24
**Status:** Ready for planning
**Source:** Direct brief from Alexis (pre-junta diagnostic session)

<domain>
## Phase Boundary

Fix the three gaps found between the deployed SEG Dashboard and the PDF design approved by Luis Santillán, before the June 25 presentation. This phase corrects real bugs and removes invented projections — it does NOT add new capabilities.

**What this phase delivers:**
1. Bug fix: `lost_reason` field mismatch so the "Oportunidades perdidas" donut shows real data
2. KPI toggle in Por Talento view (Flujo de dinero / Operativa) aligned to the approved PDF
3. Honesty fixes: funnel stage labels clarify Trello-sourced stages; revenue chart simplified to real historical data only

**What this phase does NOT deliver (conscious decisions):**
- No "Categorías de marca" section — field `d18a0b75...` is not this field in Pipedrive, no data available. To discuss with Luis.
- No future revenue projection — "Fecha de cobro" doesn't exist in Pipedrive. Chart simplified to historical only.
- No Trello card creation — `TRELLO_AUTO_CREATE_ENABLED = False` remains. `create_card()` raises `RuntimeError`. Do not change.

</domain>

<decisions>
## Implementation Decisions

### D-01: lost_reason bug — where and how to fix
- **Decision:** Diagnose across three layers: `app/models.py` (Deal column name), `app/sync/jobs.py` (Pipedrive field mapping), `app/services/kpis.py` (`talent_detail` function)
- **Root cause hypothesis:** Pipedrive delivers `lost_reason` (text); code likely reads `deal.loss_reason` (wrong name). Fix whichever layer has the mismatch.
- **Pipedrive confirmed reality:** `lost_reason` is a standard field delivered as plain resolved text (e.g. "Ya no contestó"). NOT a custom field. NOT a hash key.
- **Five valid options:** "Bateado por Talento" / "Ya no contestó" / "Cambió su estrategia de campaña" / "Ya no se hizo la campaña o evento" / "Se le hizo caro"
- **After fix:** Re-sync deals so the field populates. Verify donut in frontend shows the 5 reasons with real percentages (no more "Sin razón — 100%").

### D-02: KPI toggle in Por Talento
- **Decision:** Add a segmented control (toggle tabs) above the KPI cards in the individual talent view
- **Two views:**
  - "Flujo de dinero" (default, PDF-aligned): Campañas firmadas (count + SUM(value) of stage "Contrato y factura", status=won OR open) / Cobrado (deals linked to Trello card in "Cobranza"/"Cobrado" state) / Pendiente por cobrar (Campañas firmadas total − Cobrado)
  - "Operativa" (current): existing KPI cards unchanged
- **Colors per PDF:** azul (Campañas firmadas) / verde (Cobrado) / naranja (Pendiente)
- **Constraint:** must remain mobile-responsive; no JS frameworks

### D-03: Funnel honesty — Trello stage labels
- **Decision:** Add visual distinction so that "En ejecución" and "Cobranza" funnel stages clearly show they come from Trello, not Pipedrive
- **Implementation:** A small label/tooltip/badge (e.g. "vía Trello") next to those two stage names in the funnel display so zeros don't look like bugs
- **Pipedrive reality:** Only 4 real stages: Llamada (6), Cotización (7), Negociación (8), Contrato y factura (9). "En ejecución" and "Cobranza" come from Trello card list state.

### D-04: Revenue chart — historical only
- **Decision:** Rename "Proyección de ingresos por mes" → "Histórico de ingresos por mes"
- **Simplification:** Show only real historical data — Cobrado by `local_won_date`, Firmado by `won_time`. No invented future projections.
- **Reason:** "Fecha de cobro" does not exist in Pipedrive. Only available date fields: `expected_close_date`, `local_won_date`, `local_close_date`.

### D-05: Wave 4 (optional, only if time permits Wednesday)
- **Two optional items:**
  - Improve "Sin talento asignado: 219 deals / $14.5M" card in Resumen to be more actionable/visible
  - Verify APScheduler is running every 30 min in production and logging to SyncLog
- **Constraint:** Only if Waves 1–3 are complete with time remaining

### Claude's Discretion
- Exact UI component style for the segmented control (tabs, pill buttons, etc.) — use existing CSS patterns, dark mode consistent with dashboard
- Whether to add a tooltip or a static "(vía Trello)" text label on funnel stages — whichever is simpler with vanilla JS
- Whether `lost_reason` fix is in models.py column rename, sync mapping, or service function — diagnose first, fix at root cause

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Core files to read (diagnosis + fix)
- `app/models.py` — Deal model: check column name `loss_reason` vs `lost_reason`
- `app/sync/jobs.py` — Pipedrive→SQLite field mapping: check if `lost_reason` is mapped
- `app/services/kpis.py` — `talent_detail()` function: lost reasons + KPI computation
- `app/services/funnel.py` — 6-stage funnel logic (4 Pipedrive + 2 Trello-sourced)
- `app/integrations/pipedrive.py` — API v2 client, deal fetch/parse logic

### Frontend files to read
- `frontend/index.html` — Por Talento tab markup, KPI card structure, donut chart, funnel display
- `frontend/js/` — identify which JS module handles Por Talento rendering and the donut chart
- `frontend/css/` — existing component styles for reference when adding toggle/labels

### Project constraints
- `CLAUDE.md` — CRITICAL: read before any implementation. Contains hardcoded rules: read-only integrations, `TRELLO_AUTO_CREATE_ENABLED = False` must not change, `create_card()` must remain as `RuntimeError`

### Pipedrive field reality (confirmed against prod API v2)
- `lost_reason`: standard field, plain text, 5 options (see D-01 above)
- `d18a0b75f074043eb6d11baaf2045936e164e45b`: appears to be owner_id, NOT categoría de marca
- No "Categoría de marca" field exists in Pipedrive
- No "Fecha de cobro" field exists in Pipedrive; available date fields: `expected_close_date`, `local_won_date`, `local_close_date`
- Talents field: multi-select with options including duplas (e.g. "Don Silverio y Don Wicho")
- Pipeline stages (real): Llamada (id=6), Cotización (id=7), Negociación (id=8), Contrato y factura (id=9)

</canonical_refs>

<specifics>
## Specific Ideas

- Donut chart after fix should show percentage breakdown of the 5 reasons for lost deals per talent, matching Pipedrive's actual `lost_reason` field values
- Segmented control for KPI toggle should visually match the dark mode design system already in use
- The "Flujo de dinero" view's "Cobrado" metric relies on the Trello sync already existing (Phase 4) — the data is already in the local DB via `TrelloCard` model
- "Pendiente por cobrar" = arithmetic on already-computed values, no new DB queries needed beyond what "Campañas firmadas" and "Cobrado" already pull

</specifics>

<deferred>
## Deferred Ideas (not in this phase)

- "Categorías de marca" section in Por Talento — field doesn't exist in Pipedrive. Topic for Luis meeting.
- Future revenue projection (stacked bar: Cobrado/Proyección/Pendiente por mes) — requires "Fecha de cobro" field which doesn't exist in Pipedrive. Topic for Luis meeting.
- Webhook-based real-time sync (FUT-01) — already deferred to v2 milestone.

</deferred>

---

*Phase: 08-pre-junta-fixes*
*Context gathered: 2026-06-24 — direct brief from Alexis, pre-junta diagnostic session*
*Deadline: Wednesday 2026-06-25 (day of the Luis Santillán meeting)*
