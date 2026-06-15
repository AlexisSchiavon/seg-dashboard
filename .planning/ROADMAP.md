# Roadmap: SEG Talent Intelligence Dashboard

## Overview

This roadmap delivers the SEG Talent Intelligence Dashboard through seven strictly sequential phases (M1-M7), each building an end-to-end vertical slice (backend + DB + relevant UI) on top of the prior phase. Phase 1 establishes the FastAPI/JWT/SQLite foundation including the data-driven talent catalog. Phases 2-4 incrementally connect the three external data sources (Pipedrive, Google Sheets, Trello), each phase populating and extending the dashboard (Resumen, Por talento, Funnel, Leads) with real data as it becomes available. Phases 5-6 layer AI capabilities (PDF reports, NL query agent) on top of the now-stable services layer. Phase 7 packages and deploys the system to EasyPanel with verified persistent storage. By the end, the dashboard fully replaces the manual Pipedrive/Sheets/Trello review process with a single consolidated, AI-assisted view.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation — Auth, Talent Catalog & Health Check** - FastAPI base structure with JWT auth, SQLite (WAL), talent catalog DB table, and `/health` endpoint (completed 2026-06-11)
- [x] **Phase 2: Pipedrive Integration & Core Dashboard** - Live Pipedrive sync powers Resumen, Por talento, and Funnel tabs with real deal/revenue data (completed 2026-06-14)
- [x] **Phase 3: Google Sheets Leads Integration** - Gmail-fed leads sync populates the Leads dashboard tab (completed 2026-06-15)
- [x] **Phase 4: Trello Integration & Collection Automation** - Campaign execution/collection tracking and Pipedrive→Trello automation complete the Por talento revenue projection (completed 2026-06-15)
- [ ] **Phase 5: AI-Generated PDF Reports** - Claude-narrated monthly reports with downloadable history in the Reportes tab
- [ ] **Phase 6: Embedded Natural-Language Agent** - Read-only conversational querying of dashboard data
- [ ] **Phase 7: Docker & EasyPanel Deployment** - Containerized deployment with persistent SQLite storage verified across redeploys

## Phase Details

### Phase 1: Foundation — Auth, Talent Catalog & Health Check

**Goal**: A secure, runnable FastAPI application exists with JWT-protected endpoints, a database-driven talent catalog, and a health check — the foundation every later module builds on.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, TAL-01, TAL-02
**Success Criteria** (what must be TRUE):

  1. User can log in with email/password and receive a JWT that authorizes subsequent requests
  2. Requests to protected endpoints without a valid JWT are rejected (401)
  3. `GET /health` returns service status without authentication
  4. The 21 initial talents are stored in the database and can be listed/added/edited without code changes
  5. Each talent record can be mapped to one or more Pipedrive product IDs (field exists and is settable, even if Pipedrive sync isn't live yet)

**Plans**: 3 plans
Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Walking Skeleton: scaffold, config, DB (WAL), models, Alembic, admin seed, login/logout cookie auth + login UI, test infra (AUTH-01, AUTH-02)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Talent catalog vertical slice: protected CRUD + product mapping endpoints, idempotent 21-talent seed (TAL-01, TAL-02)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — Public /health, change-password + create-user endpoints, frontend 401→login redirect (AUTH-02, AUTH-03)

**UI hint**: yes

### Phase 2: Pipedrive Integration & Core Dashboard

**Goal**: Pipedrive deal data flows into local SQLite on a schedule (and on-demand), and the dashboard's Resumen, Por talento, and Funnel tabs display real, computed revenue/funnel data per talent.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, DASH-01, DASH-02, DASH-03
**Success Criteria** (what must be TRUE):

  1. Deals (stage, value, product, custom fields) sync from Pipedrive into local SQLite, both on a schedule and via a manual "sync now" action
  2. Each deal's product maps to a talent and its 70% commission is computed automatically; deals at $0 MXN display as "Sin cotizar"
  3. Each deal captures razón de pérdida, categoría de marca, and fecha de cobro esperada from Pipedrive custom fields
  4. The Resumen tab shows global KPIs, talent ranking by revenue, and a recent activity feed sourced from real Pipedrive data
  5. The Funnel tab shows all 6 stages (Llamada → Cotización → Negociación → Contrato → En ejecución → Cobranza) with deal count, amount, and bottleneck detection
  6. The Por talento tab shows per-talent KPIs, individual funnel, lost opportunities (with reason), and brand category breakdown from real data (revenue projection/collection calendar/campaign table land in Phase 4 once Trello data is available)

**Plans**: 3 plans
Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Pipedrive v2 sync vertical slice: Deal/DealStageEvent/SyncLog models + migration, x-api-token client, sync job (commission/Sin-cotizar/custom-fields/event-diffing), hourly scheduler, "Sincronizar ahora" + "Última sync" indicator, talent↔product auto-match (PIPE-01..05)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Resumen + Funnel dashboard slice: kpis/funnel services, /dashboard/summary + /dashboard/funnel endpoints, global KPIs + talent ranking + activity feed + 6-stage funnel + bottleneck detection (DASH-01, DASH-03)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-03-PLAN.md — Por talento dashboard slice: talent_detail service, /dashboard/talents/{id} endpoint, per-talent KPIs/funnel, brand-category donut (by deal count), lost opportunities by reason (DASH-02)

**UI hint**: yes

### Phase 3: Google Sheets Leads Integration

**Goal**: Leads captured in the Gmail-fed Google Sheet are synced into local SQLite and visible in the dashboard, classified by talent, source, and status.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: SHEET-01, SHEET-02, DASH-04
**Success Criteria** (what must be TRUE):

  1. Leads from the configured Google Sheet sync into local SQLite on the same schedule/manual-sync pattern as Pipedrive
  2. Each synced lead is classified by talent, source, and status
  3. The Leads tab displays all synced leads, filterable/grouped by talent, source, and status

**Plans**: 3 plans
Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Sheets→SQLite leads sync vertical slice: Lead model + migration, read-only gspread integration, classification service (QUALIFIED_STATUS), sync_sheets upsert by sheet_row_id, scheduler + manual-sync wiring, /leads/summary endpoint (SHEET-01, SHEET-02)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — Leads tab UI vertical slice: leads_list filterable endpoint, #page-leads tab, leads.js with per-talent bars + score pills + talent/source/status filters (DASH-04, SHEET-02)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-03-PLAN.md — Resumen tab Leads KPI tiles: extend /dashboard/summary with leads_totales + calificados, wire "Leads totales"/"Calificados" tiles (DASH-04)

**UI hint**: yes

### Phase 4: Trello Integration & Collection Automation

**Goal**: Campaign execution and collection state from Trello is synced and linked to Pipedrive deals, completing the Por talento revenue projection (cobrado/proyección/pendiente) and collection calendar, with automatic Trello card creation when a deal is won.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: TRELLO-01, TRELLO-02, TRELLO-03, DASH-02
**Success Criteria** (what must be TRUE):

  1. Trello cards for deals with signed contracts sync into local SQLite, distinguishing "en ejecución" from "en cobranza"
  2. Synced Trello cards display their expected collection date
  3. When a Pipedrive deal is marked "ganado", a Trello card is automatically created with the expected collection date (verified via reconciliation, not just a one-shot webhook)
  4. The Por talento tab now shows the monthly revenue projection as stacked bars (cobrado/proyección/pendiente), a collection calendar, top 3 campaigns of the month, and the full campaign table (campaign/status/amount) — completing DASH-02

**Plans**: 4 plans
Plans:
**Wave 1**

- [x] 04-01-PLAN.md — TrelloCard model + migration, trello.py httpx wrapper (LIST_STATE_MAP), Wave 0 test stubs (TRELLO-01)

**Wave 2** *(blocked on Wave 1)*

- [x] 04-02-PLAN.md — sync_trello read+upsert: deal linkage (desc id + fuzzy match), collection-date fallback, scheduler + manual-trigger wiring (TRELLO-01, TRELLO-02)

**Wave 3** *(blocked on Wave 2)*

- [x] 04-03-PLAN.md — Auto-creation reconciliation: won deals → Contrato-list card with [seg:deal_id=N] marker, idempotency guard (TRELLO-03)

**Wave 4** *(blocked on Wave 2)*

- [x] 04-04-PLAN.md — Por talento DASH-02 slice: income_projection/payment_calendar/deals service, extended TalentDetail endpoint, frontend render wiring (DASH-02)

**UI hint**: yes

### Phase 5: AI-Generated PDF Reports

**Goal**: Users can generate AI-narrated monthly PDF reports per talent (or all talents) using Claude, with all financial figures computed in Python and only narrated by the AI, and browse/download report history.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: REPORT-01, REPORT-02, DASH-05
**Success Criteria** (what must be TRUE):

  1. User can trigger generation of a monthly PDF report for a single talent or for all talents
  2. Generated PDF contains figures computed entirely in Python (KPIs, funnel, revenue) with Claude providing only narrative text — no AI-invented numbers
  3. The Reportes tab lists previously generated reports and allows downloading any of them

**Plans**: TBD
**UI hint**: yes

### Phase 6: Embedded Natural-Language Agent

**Goal**: Users can ask natural-language questions about dashboard data (revenue, funnel, leads, talents) and receive accurate, read-only answers via an embedded conversational agent.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: AGENT-01
**Success Criteria** (what must be TRUE):

  1. User can open an embedded chat interface within the dashboard and ask questions in natural language about revenue, funnel, leads, or talent performance
  2. Agent responses are based on real computed data via tool-calling against existing services (never invented figures, never raw DB dumps)
  3. Agent cannot perform any write/mutating actions against Pipedrive, Trello, Sheets, or the local database

**Plans**: TBD
**UI hint**: yes

### Phase 7: Docker & EasyPanel Deployment

**Goal**: The full application runs in Docker and is deployed to EasyPanel with a persistent SQLite volume that survives redeploys.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: DEPLOY-01, DEPLOY-02
**Success Criteria** (what must be TRUE):

  1. `docker compose up` builds and runs the full application (API + frontend + scheduler) from a single Dockerfile/docker-compose.yml
  2. The application is deployed and reachable on EasyPanel
  3. The SQLite database file persists across a redeploy on EasyPanel (verified by an explicit redeploy test showing data survives)

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation — Auth, Talent Catalog & Health Check | 3/3 | Complete   | 2026-06-11 |
| 2. Pipedrive Integration & Core Dashboard | 3/3 | Complete   | 2026-06-14 |
| 3. Google Sheets Leads Integration | 3/3 | Complete   | 2026-06-15 |
| 4. Trello Integration & Collection Automation | 4/4 | Complete   | 2026-06-15 |
| 5. AI-Generated PDF Reports | 0/TBD | Not started | - |
| 6. Embedded Natural-Language Agent | 0/TBD | Not started | - |
| 7. Docker & EasyPanel Deployment | 0/TBD | Not started | - |
