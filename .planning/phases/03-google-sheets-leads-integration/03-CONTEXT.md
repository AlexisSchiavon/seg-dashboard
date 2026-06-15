# Phase 3: Google Sheets Leads Integration - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Leads captured in the existing Gmail-fed Google Sheet (18-column structure, already live with real data) are synced into local SQLite and surfaced in the dashboard's Leads tab, classified by talent, source, and status. The Resumen tab's "Leads totales" and "Calificados" KPI tiles are also wired up with this data in this phase.

</domain>

<decisions>
## Implementation Decisions

### Google Sheet Structure (SHEET-01)
- **D-29:** The Google Sheet already exists and contains real data — no schema design needed. Auth via `GOOGLE_SERVICE_ACCOUNT_JSON` env var using `gspread.service_account_from_dict()`.
- **D-30:** Sync only the 10 core columns needed for the UI (lean model): `ID_Lead`, `Remitente_Nombre`, `Remitente_Email`, `Asunto`, `Fecha_Recepcion`, `Talento_Mencionado`, `Status_Filtrado`, `Score_Calidad`, `Bloqueado`, `Convertido_a_Prospecto`. The 8 remaining columns (`Email_Completo`, `Categoria_Detectada`, `Razon_validacion`, `Respuesta_Enviada`, `Fecha_Respuesta`, `Link_WhatsApp_Generado`, `ID_Prospecto`, `Threadid`) are ignored for now.
- **D-31:** Sync frequency and trigger: **same pattern as Pipedrive** — hourly automatic sync + manual "Sincronizar ahora" button (D-20/D-22 carry forward). Sheets sync runs alongside or as part of the same sync job.

### Talent Attribution (SHEET-02)
- **D-32:** Talent attribution comes from the `Talento_Mencionado` column. Match strategy is **name-based auto-match** — same logic as Pipedrive's D-16 (talent.name ≈ Talento_Mencionado, exact/near-exact). No separate alias table needed.
- **D-33:** Leads where `Talento_Mencionado` is empty or doesn't match any talent in the DB are **still synced** and grouped under a **"Sin talento asignado"** bucket — consistent with D-17 from Phase 2. They count in global totals but not per-talent KPIs.

### Status & Source Taxonomy (SHEET-02)
- **D-34:** The actual values in `Status_Filtrado` are **unknown** — researcher must enumerate distinct values from the live Sheet before planning (read a sample of rows or use `pandas`/`gspread` to get unique values). The planner maps those values to the UI's display buckets.
- **D-35:** `fuente` (source) is stored **explicitly** on the Lead model even though all Phase 3 leads come from Gmail (value = `"Gmail"`). This makes the model extensible for Phase 4 prospecting leads or future channels without a migration.
- **D-36:** `Score_Calidad` is displayed as a **colored pill/badge** next to each lead row in the Leads tab list: 0–40 → red, 41–70 → amber, 71–100 → green. Researcher confirms the actual score range from live data.

### Resumen Tab Leads KPIs (DASH-01 partial, previously deferred)
- **D-37:** Phase 3 **wires up** the "Leads totales" and "Calificados" KPI tiles on the Resumen tab (previously placeholders per D-28). The data is now available and the tiles already exist in the UI.
- **D-38:** The definition of "Calificado" (which `Status_Filtrado` value(s) count) is **delegated to researcher** — researcher reads distinct Status_Filtrado values from the live Sheet and identifies the qualifying status. Planner codifies the mapping as a constant/enum in `app/services/`.

### Claude's Discretion
- **"Leads por talento" bar section** — mockup shows bars with `count · calificados` per talent. Sorting (by total leads vs. by qualified count) and pagination (show all 21 vs. top N) left to planner based on the mockup reference.
- **`Bloqueado` and `Convertido_a_Prospecto` fields** — synced but not yet surfaced in the UI (Phase 3 is read-only display). Whether to visually flag blocked/converted leads is planner's call; a subtle pill or greyed-out state are both consistent with the design system.
- **Filtering depth** — ROADMAP says "filterable/grouped by talent, source, and status". Implementation (dropdown vs. chip-based filter, URL-param state) left to planner; follow the Vanilla JS patterns already established in `dashboard.js`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Sheet Integration
- `.planning/research/STACK.md` — confirms `gspread>=6.1` + `google-auth>=2.40` for service-account auth (`gspread.service_account_from_dict()`); do NOT use deprecated `oauth2client` patterns.
- `.planning/research/ARCHITECTURE.md` — modular structure; new integration goes in `app/integrations/sheets.py`, service logic in `app/services/` (follow the `funnel.py`/`kpis.py` pattern from Phase 2).

### Business Logic & Requirements
- `.planning/REQUIREMENTS.md` — SHEET-01, SHEET-02, DASH-04 (Phase 3 scope); DASH-01 partial (Leads totales / Calificados KPIs on Resumen).
- `.planning/PROJECT.md` §Context — 21 talent names used for Talento_Mencionado name-matching (same list as Pipedrive auto-match).

### Phase 2 Foundation (prior decisions this phase builds on)
- `.planning/phases/02-pipedrive-integration-core-dashboard/02-CONTEXT.md` — D-16 (name-based auto-match strategy), D-17 ("Sin talento asignado" bucket), D-20/D-21/D-22/D-23/D-24 (sync schedule, "Sincronizar ahora" button, async sync UX, failure banner — all carry forward unchanged).

### UI Reference
- `.planning/reference/mockup.html` — `#page-leads` section: KPI grid (3 tiles), "Leads por talento" source-bar rows (`.source-row`/`.source-bar-track`/`.source-bar-fill`), "Leads recientes" list (`.deal-row`/`.pill` patterns). Also `#page-overview` for the placeholder Leads totales / Calificados KPI tiles to wire up.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/integrations/base.py` (`get_with_retry`, `paginate`) — retry/backoff helpers; `sheets.py` may reuse `get_with_retry` pattern or adapt for gspread's own retry semantics.
- `app/integrations/pipedrive.py` — thin `httpx` wrapper pattern to mirror for `sheets.py` (typed Pydantic response models, no raw dicts).
- `app/auth/dependencies.py` (`get_current_user`) — protect new `/leads` router with the same dependency.
- `app/sync/jobs.py` (Phase 2 scheduler) — Sheets sync should hook into the same scheduler rather than creating a separate job runner.
- `mockup.html` CSS classes ready to reuse: `.source-row`/`.source-icon`/`.source-info`/`.source-bar-track`/`.source-bar-fill`/`.source-pct` (leads-per-talent bars), `.deal-row`/`.pill` (lead list rows), `.kpi` grid (Leads totales / Calificados tiles on Resumen and Leads tab).

### Established Patterns
- SQLAlchemy 2.0 declarative models (`Mapped`/`mapped_column`) + Alembic migration for the new `leads` table.
- Sync runs upsert by natural key (`ID_Lead` from the Sheet → `sheet_lead_id` on the model); same pattern as `pipedrive_id` on `Deal`.

### Integration Points
- New `Lead` SQLAlchemy model in `app/models.py` — columns: `id` (PK), `sheet_lead_id` (unique, from `ID_Lead`), `remitente_nombre`, `remitente_email`, `asunto`, `fecha_recepcion`, `talent_id` (FK → talents, nullable), `status_filtrado`, `fuente` (default `"Gmail"`), `score_calidad` (nullable int), `bloqueado` (bool), `convertido_a_prospecto` (bool).
- New `app/integrations/sheets.py` — gspread wrapper returning typed Pydantic models per row.
- New `app/services/leads.py` — classification logic (talent match, status mapping, Calificados definition).
- New `app/routers/leads.py` — protected endpoints for the Leads tab (`GET /leads`, grouped/filtered by talent/source/status).
- `app/routers/dashboard.py` — extend existing summary endpoint to include Leads totales / Calificados counts (D-37).

</code_context>

<specifics>
## Specific Ideas

- The 18 Sheet columns are known verbatim (D-30). Researcher should verify header row matches exactly before building the column→field mapping.
- `Score_Calidad` color thresholds (0–40 red / 41–70 amber / 71–100 green) use the existing CSS variables: `--redT` / `--amberT` / `--greenT` — no new colors needed.
- `fuente` field defaults to `"Gmail"` for all Phase 3 leads. When Phase 4 adds Trello/prospecting leads, the field is already in the schema.

</specifics>

<deferred>
## Deferred Ideas

- **`Categoria_Detectada` column** — potentially maps to brand category (Moda/Retail, Alimentos, etc.) like the Pipedrive brand_category field. Not synced in Phase 3 (not in core set). Worth revisiting in Phase 4 or 5 if cross-source brand category analysis is needed.
- **`ID_Prospecto` linkage** — this column likely holds a Pipedrive deal or person ID for converted leads. A Sheets ↔ Pipedrive lead-to-deal join is out of Phase 3 scope. Could enable cross-source conversion tracking in a future phase.
- **`Link_WhatsApp_Generado`** — implies an automated WhatsApp outreach flow exists outside this dashboard. Not surfaced in Phase 3. Could feed a future "outreach status" view.
- **`Bloqueado` and `Respuesta_Enviada` filtering** — might warrant a dedicated "responded / blocked" view or filter facet. Deferred to Phase 4 or 5 once real usage patterns emerge.

None of these are new capabilities requested during discussion — they emerged from inspecting the Sheet schema.

</deferred>

---

*Phase: 3-google-sheets-leads-integration*
*Context gathered: 2026-06-14*
