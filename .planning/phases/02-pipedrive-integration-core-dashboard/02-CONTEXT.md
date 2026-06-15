# Phase 2: Pipedrive Integration & Core Dashboard - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Pipedrive deal data (stages, value, products, custom fields) syncs into local SQLite on an hourly schedule plus an on-demand "sync now" trigger. Each deal's product maps to a talent (via a one-time name-based auto-match seeding `talent_products.pipedrive_product_id`, left null in Phase 1) with 70% commission computed automatically and $0 MXN deals classified as "Sin cotizar". The Resumen, Por talento, and Funnel dashboard tabs render this real data: global KPIs, talent ranking, recent activity feed, full 6-stage funnel with bottleneck detection, and per-talent KPIs/funnel/lost-opportunities/brand-category breakdown.

</domain>

<decisions>
## Implementation Decisions

### Mapeo talento↔producto Pipedrive (TAL-02 / PIPE-02)
- **D-16:** Mapping strategy is **name-based auto-match, 1:1** — each talent corresponds to exactly one Pipedrive product; match on talent.name ≈ Pipedrive product name (exact/near-exact). No need to handle one-talent-to-many-products in the matching logic (the `talent_products` schema still supports it, but matching assumes 1:1).
- **D-17:** Deals whose Pipedrive product does NOT match any talent are still synced and counted in global totals, grouped under a **"Sin talento asignado"** bucket. They do not affect per-talent KPIs.
- **D-18:** A report/list of **unmapped Pipedrive products** is generated for manual review.
- **D-19:** The auto-match runs as a **one-time setup script** (not on every sync, not via new UI). Corrections to mismatches go through the existing `/talents/{id}/products` CRUD endpoints from Phase 1 — no new admin UI for this.

### Frecuencia de sync y 'sync now' (PIPE-01)
- **D-20:** Automatic Pipedrive sync runs **every hour**.
- **D-21:** A persistent **"Última sync: hace X min"** indicator replaces (or augments) the mockup's "En vivo" pill in the top nav, visible across all tabs.
- **D-22:** A **"Sincronizar ahora"** button lives on the Resumen tab.
- **D-23:** Manual sync is **async** — button shows "Sincronizando..." and the user can keep navigating; a toast notifies on completion ("Sync completado — X deals actualizados").
- **D-24:** If sync fails (Pipedrive down, bad token, rate limit), show a **visible warning banner** ("No se pudo sincronizar — mostrando datos de hace X horas") while continuing to display the last successfully synced data.

### Oportunidades perdidas y categorías de marca (Por talento — DASH-02)
- **D-25:** "Oportunidades perdidas" = a **list of lost deals** (brand, amount, pill showing razón de pérdida) **plus a summary count per reason** above the list (e.g., "3 por presupuesto, 2 por timing").
- **D-26:** "Categorías de marca" breakdown uses a **donut chart + legend**, reusing the `.donut-wrap`/`.donut-legend` CSS classes already defined (but unused) in `mockup.html`.
- **D-27:** The donut measures **% by number of deals** (not by revenue amount).
- **D-28:** Both new sections **replace the "Fuente de leads" position** in the Por talento tab (that section has no data source until Phase 3 / Sheets integration). Resulting order: KPIs → Funnel → Deals activos → Categorías de marca (donut) → Oportunidades perdidas.

### Claude's Discretion
- **Resumen sections with no data source yet** (Insights IA — Claude/M5-6; "Leads totales"/"Calificados"/"Fuente de leads" KPIs — Sheets/M3) were NOT discussed (user didn't select this area). ROADMAP Phase 2 only promises global KPIs/ranking/activity feed from real Pipedrive data — planner should decide how to handle these mockup elements (hide vs. "Próximamente" placeholder vs. omit from Phase 2's Resumen entirely) without inventing new scope.
- **Bottleneck detection definition** (DASH-03, Funnel tab) — not discussed. Mockup hints at two possible heuristics: stage-to-stage conversion % below an industry benchmark ("41% vs 60%"), or deals stuck >14 days without activity. Researcher/planner should pick one or combine, grounded in available Pipedrive data (stage timestamps).
- **"Actividad reciente" feed source** (DASH-01) — not discussed. Mockup shows deal stage-change events sourced from Pipedrive. Researcher/planner should define how this is derived: diff of stage changes detected during sync (store a lightweight events table) vs. polling Pipedrive's Activities API.
- **Scheduler mechanism** for the hourly sync (D-20) — APScheduler, system cron, or FastAPI background task. Researcher/planner decides per ARCHITECTURE.md and the eventual Docker/EasyPanel deploy (Phase 7).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Tech Stack & Known Pitfalls
- `.planning/research/PITFALLS.md` — Pipedrive custom fields are referenced by hashed keys, must resolve via the `dealFields` endpoint at startup; watch for pagination/2000-result cap on deal sync. Directly governs PIPE-01/PIPE-04 implementation.
- `.planning/research/STACK.md` — confirms no official Pipedrive SDK; use `httpx` + a thin typed wrapper in `app/integrations/pipedrive.py`.
- `.planning/research/ARCHITECTURE.md` — modular structure (`app/integrations/`, `app/services/`, `app/routers/`) that Phase 2's Pipedrive sync and dashboard services must follow.

### Business Logic & Requirements
- `.planning/PROJECT.md` §Context — Pipedrive business logic: talento=producto, 70% comisión fija, $0 MXN = "Sin cotizar", 6-stage funnel (Llamada → Cotización → Negociación → Contrato → En ejecución → Cobranza), 5 razones de pérdida, 6 categorías de marca.
- `.planning/REQUIREMENTS.md` — PIPE-01 through PIPE-05, DASH-01/DASH-02/DASH-03 (Phase 2 scope).

### Phase 1 Foundation (prior decisions this phase builds on)
- `.planning/phases/01-foundation-auth-talent-catalog-health-check/01-CONTEXT.md` — D-14/D-15: `talent_products` normalized join table with `pipedrive_product_id` left null, to be populated per D-16–D-19. Auth pattern (`get_current_user` dependency) to protect new routers.

### UI Reference
- `.planning/reference/mockup.html` — visual reference for Resumen/Por talento/Funnel tabs. Contains the unused `.donut-wrap`/`.donut-legend` CSS (D-26), `.activity-row` pattern (activity feed), `.alert.warn`/`.alert.info` pattern (bottleneck + sync-failure banners, D-24), and the "En vivo" nav pill to be repurposed (D-21).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/auth/dependencies.py` (`get_current_user`) — protects new Pipedrive sync and dashboard routers, same pattern as Phase 1's `/talents` router.
- `app/routers/talents.py` + `/talents/{id}/products` CRUD (Phase 1) — used as-is for correcting auto-match mismatches (D-19); no new admin UI needed.
- `mockup.html` CSS classes ready to reuse: `.funnel-row`/`.f-track`/`.f-fill` (funnel bars), `.rank-row` (talent ranking), `.deal-row`/`.pill` (deals + lost-opportunities lists), `.donut-wrap`/`.donut-legend` (brand category breakdown), `.activity-row` (activity feed), `.alert.warn`/`.alert.info` (banners).

### Established Patterns
- SQLAlchemy 2.0 declarative models (`app/models.py`) with `Mapped`/`mapped_column`, Alembic migrations, sync `httpx.Client` per STACK.md — the new `app/integrations/pipedrive.py` and `app/services/` modules should follow the same conventions.

### Integration Points
- `app/integrations/pipedrive.py` (new) — httpx wrapper for Pipedrive `deals`, `products`, `dealFields` endpoints.
- `app/services/funnel.py`, `app/services/kpis.py` (new, per CLAUDE.md folder structure) — compute commission/funnel/bottleneck/KPIs consumed by `app/routers/dashboard.py` (new).
- `talent_products` table (Phase 1 schema) — populated by the one-time auto-match script (D-16/D-19).

</code_context>

<specifics>
## Specific Ideas

- The 21 talent names already seeded in Phase 1 (from `PROJECT.md` Context) are the basis for the name-based auto-match against Pipedrive's product catalog (D-16).
- 5 razones de pérdida (PROJECT.md): Presupuesto insuficiente, No respondieron, Eligieron otro talento, Campaña cancelada, Sin fit estratégico — feed the D-25 per-reason summary.
- 6 categorías de marca (PROJECT.md): Moda/Retail, Alimentos/Restaurantes, Agencias, Medios y Entretenimiento, Educación/Gobierno, Otros — feed the D-26/D-27 donut.

</specifics>

<deferred>
## Deferred Ideas

- **Resumen tab scope for sections without a data source yet** (Insights IA, Leads/Calificados KPIs, Fuente de leads donut on Resumen) — this gray area was offered but not selected for discussion. Left to planner discretion (see Claude's Discretion above); not a new phase, just an open implementation question within Phase 2's existing scope.

None else — discussion stayed within phase scope, no new-capability scope creep arose.

</deferred>

---

*Phase: 2-pipedrive-integration-core-dashboard*
*Context gathered: 2026-06-11*
