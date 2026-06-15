# Phase 4: Trello Integration & Collection Automation - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Campaign execution and collection state from a single Trello board is synced into local SQLite and linked to Pipedrive deals, completing the "Por talento" tab: revenue projection chart (cobrado/proyección/pendiente), collection calendar, top 3 campaigns, and full campaign table. A Pipedrive→Trello automation creates a card (with deal ID stored as custom field) when a deal is marked "ganado".

</domain>

<decisions>
## Implementation Decisions

### Trello Board Structure (TRELLO-01)
- **D-39:** There is **one board** for all talents (not one per talent). `TRELLO_BOARD_IDS` env var already contains the board ID — researcher reads it from `.env`, no discovery needed.
- **D-40:** List-to-state mapping (researcher must confirm exact list names via API):
  - `"Contrato"`, `"Firmar contrato (todos)"`, `"Enviar factura"` → **En ejecución**
  - `"Cobrar"`, `"Enviar encuesta"` → **En cobranza**
  - `"Finalizados"` → **Cerrado/Cobrado**
  - `"Otros pendientes"` → **Ignorar** (not synced)
- **D-41:** Sync only cards from the lists above. Cards in any other list are ignored. Researcher enumerates all board lists via API and verifies these exact names before planning.

### Deal ↔ Trello Card Linkage (TRELLO-02)
- **D-42:** **Primary match strategy: card name ≈ Pipedrive deal title** (same fuzzy/exact approach as D-16 for talent name matching). Researcher verifies consistency of naming in the real board before planning.
- **D-43:** When the automation **creates** a card (deal won in Pipedrive → new Trello card), it **stores the Pipedrive deal ID as a Trello custom field** on the card. This enables precise bidirectional reconciliation in future syncs — matching by custom field takes precedence over title match.
- **D-44:** **Collection date location** is **unknown** — researcher inspects real Trello cards to determine whether it's the Trello due date, a custom field, or in the description/comments. Researcher documents which field to use before planning. New `TrelloCard` model must accommodate whichever field is found.

### Automation Trigger (TRELLO-03)
- **D-45:** Automation is **polling-based** (no Pipedrive webhook), consistent with the existing sync architecture (D-20/D-22). The sync job detects deals newly transitioned to stage `"Cobrado"` or `won_at` populated since last sync, and creates the Trello card. Reconciliation means: each sync run checks whether a won deal already has a linked Trello card (by custom field or title match) before creating a duplicate.
- **D-46:** The new Trello card is created in the **`"Contrato"`** list (first "En ejecución" list) — the starting point for a newly won campaign entering the execution flow. Researcher confirms this is the correct entry list.

### Revenue Projection Logic (DASH-02)
- **D-47:** Three-layer projection using **venta_total** (full deal value, not 70% commission) for all layers:
  - **Cobrado** (green): cards in `"Finalizados"` Trello list
  - **Proyección / Firmado** (blue): deals in Pipedrive stages `"Contrato"` or `"En ejecución"` (Trello lists: Contrato / Firmar contrato / Enviar factura)
  - **Pendiente** (amber): cards in Trello lists `"Cobrar"` or `"Enviar encuesta"`
- **D-48:** **Date grouping:** researcher compares coverage of `expected_collection_date` (Pipedrive custom field, already in `Deal` model) vs Trello card collection date field (D-44) and uses whichever has better data population. Document the choice in PLAN.md.
- **D-49:** **Window:** 4 months — **1 month prior** (real/historical) + **current month** + **2 future months** (projected). Sliding window anchored to today.
- **D-50:** Per-talent projection endpoint returns `income_projection: [{month, cobrado, proyeccion, pendiente}]` and `payment_calendar: [{month, amount}]` — the frontend already consumes these field names (`renderIncomeProjection` and `renderPaymentCalendar` functions exist and expect this structure).

### Frontend Integration (DASH-02 — frontend already built)
- **D-51:** The Por talento tab redesign is **already implemented** (frontend/index.html + styles.css + dashboard.js, committed 2026-06-14). The `/dashboard/talents/{id}` endpoint needs to add `income_projection`, `payment_calendar` to its response. The `top-campaigns` section uses individual deal rows (not stage aggregates as now). The `talent-deals` table also uses individual deals.
- **D-52:** Campaign table individual deal data: researcher checks if adding a `/dashboard/talents/{id}/deals` endpoint or extending the existing endpoint is the cleaner approach given the current `TalentDetail` schema.

### Sync Pattern (carries forward from Phase 2)
- **D-20 (carry):** Hourly automatic sync + manual "Sincronizar ahora" — Trello sync hooks into the same `jobs.py` scheduler, not a separate runner.
- **D-22 (carry):** Same toast/banner UX for sync errors (D-23/D-24).

### Claude's Discretion
- **Talent attribution for Trello cards:** Card name contains the deal title but may not explicitly name the talent. Attribution falls through to the linked Pipedrive deal's talent (via deal ID custom field or title match). If no match, card goes to "Sin talento asignado" bucket (D-17 carry).
- **Duplicate card guard:** If a deal is already linked to a Trello card (by custom field), the automation skips creation. Implementation detail left to planner.
- **`"Enviar encuesta"` list:** Whether "Enviar encuesta" cards count toward collection amounts or just toward "has been invoiced" status is left to planner's judgment based on the real data.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Trello Integration
- `.planning/REQUIREMENTS.md` — TRELLO-01, TRELLO-02, TRELLO-03, DASH-02 (Phase 4 scope)
- `.planning/PROJECT.md` §Context / "Lógica de negocio — Trello" — business rules for card creation, ejecución vs cobranza, collection dates
- `.env` (read-only, never commit) — `TRELLO_API_KEY`, `TRELLO_TOKEN`, `TRELLO_BOARD_IDS` — all credentials present; researcher reads board ID from here

### Prior Phase Foundation
- `.planning/phases/02-pipedrive-integration-core-dashboard/02-CONTEXT.md` — D-16 (name-match strategy), D-17 (Sin talento asignado), D-20/D-22/D-23/D-24 (sync schedule, manual button, UX patterns — all carry forward)
- `.planning/phases/03-google-sheets-leads-integration/03-CONTEXT.md` — D-31 (sheets sync hooks into same job runner pattern)

### Frontend Already Built (researcher must read before planning)
- `frontend/index.html` — Por talento tab structure: `#income-projection`, `#payment-calendar`, `#top-campaigns`, `#talent-deals` containers
- `frontend/js/dashboard.js` — `renderIncomeProjection(data)`, `renderPaymentCalendar(data)`, `renderTopCampaigns(stages)`, `renderCampaignTable(stages, lostOpps)` — expected data shapes are defined by these functions
- `frontend/css/styles.css` — `.medal-card`, `.ctable-row`, `.sbadge`, `.proj-chart`, `.timeline` — CSS already exists

### Existing Backend (researcher must read)
- `app/models.py` — `Deal` model has `expected_collection_date: Mapped[str | None]` already; researcher notes this before designing `TrelloCard` model
- `app/integrations/pipedrive.py` + `app/integrations/sheets.py` — thin httpx wrapper pattern to mirror for `app/integrations/trello.py`
- `app/sync/jobs.py` — scheduler; Trello sync hooks in here (same as Sheets)
- `app/routers/dashboard.py` — existing `/dashboard/talents/{id}` endpoint to extend with `income_projection` + `payment_calendar`

### Stack Reference
- `.planning/research/STACK.md` — httpx thin wrapper preferred over `py-trello` (unmaintained); Trello auth = `?key=…&token=…` query params

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/integrations/base.py` (`get_with_retry`, `_paginate`) — retry/backoff helpers; `trello.py` should follow the same pattern
- `app/integrations/pipedrive.py` — thin httpx wrapper model to mirror exactly for `app/integrations/trello.py`
- `app/sync/jobs.py` — APScheduler setup; add Trello sync as a new job function alongside `sync_pipedrive` and `sync_sheets`
- `app/auth/dependencies.py` (`get_current_user`) — protect any new Trello-facing endpoints with the same dependency
- `frontend/js/dashboard.js` `loadTalentDetail()` — already calls `renderIncomeProjection(data.income_projection || null)` and `renderPaymentCalendar(data.payment_calendar || null)`; backend just needs to populate these fields

### Established Patterns
- SQLAlchemy 2.0 declarative models (`Mapped`/`mapped_column`) + Alembic migration for the new `TrelloCard` model
- Upsert by natural key (`trello_card_id`) — same pattern as `pipedrive_id` on `Deal` and `sheet_lead_id` on `Lead`
- Concurrency guard in `sync_pipedrive`/`sync_sheets` by source — `sync_trello` needs the same per-source guard (CR-03 from Phase 3 code review)

### Integration Points
- New `TrelloCard` SQLAlchemy model: `id` (PK), `trello_card_id` (unique), `name`, `list_name`, `list_state` (enum: ejecucion/cobranza/cerrado), `deal_id` (FK → deals, nullable), `pipedrive_deal_id_custom` (str, nullable — from Trello custom field), `collection_date` (date, nullable — researcher determines source), `synced_at`
- New `app/integrations/trello.py` — httpx wrapper; methods: `get_board_lists()`, `get_cards_in_list()`, `create_card()`, `set_custom_field()`
- New `app/services/trello_service.py` (or extend existing) — projection math: grouping deals+cards by month and layer (cobrado/proyeccion/pendiente)
- `/dashboard/talents/{id}` endpoint — add `income_projection: list[MonthProjection]`, `payment_calendar: list[CalendarEntry]`, and full individual `deals: list[DealRow]` to response
- `app/sync/jobs.py` — add `sync_trello()` job; detect won deals missing a Trello card and create them

</code_context>

<specifics>
## Specific Ideas

- The frontend chart `renderIncomeProjection` expects: `[{month: "Jun 2026", cobrado: 1200000, proyeccion: 3500000, pendiente: 800000}]`
- The frontend calendar `renderPaymentCalendar` expects: `[{month: "Jun 2026", amount: 500000}]`
- The frontend `renderTopCampaigns(stages)` currently uses funnel stage aggregates — Phase 4 should replace with real individual deal rows sorted by `venta_total` desc; top 3 by amount
- Trello API auth: `?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}` query params on every request — no OAuth flow needed
- Custom field for Pipedrive deal ID on auto-created cards: researcher determines if Power-Ups / custom fields are enabled on the board, and what field ID to use (or create)

</specifics>

<deferred>
## Deferred Ideas

- **Webhook-based real-time sync** — Using Pipedrive webhooks for instant Trello card creation (instead of polling) is more responsive but adds complexity (endpoint, signature validation, retry queue). Deferred to post-Phase 7 if polling latency becomes a problem.
- **`Categoria_Detectada` cross-source** — Linking Google Sheets lead categories to Trello campaign brand categories (noted in Phase 3 deferred). Still out of scope here.
- **Per-talent Trello board** — If SEG ever wants separate boards per talent, the `list_state` enum + board abstraction in `trello.py` should make this a config change. Not needed now.
- **"Enviar encuesta" as "Cobrado"** — If the team later decides that sending the survey = collection confirmed, the list mapping in D-40 becomes a config constant, not code. Noted for future.

</deferred>

---

*Phase: 04-trello-integration-collection-automation*
*Context gathered: 2026-06-14*
