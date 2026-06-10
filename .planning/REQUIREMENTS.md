# Requirements: SEG Talent Intelligence Dashboard

**Defined:** 2026-06-09
**Core Value:** Dar visibilidad consolidada y en tiempo real del funnel comercial e ingresos por talento — reemplazando el proceso manual disperso entre Pipedrive, Sheets y Trello.

## v1 Requirements

Requirements for initial release (M1-M7, built incrementally). Each maps to roadmap phases.

### Auth & Base (M1)

- [ ] **AUTH-01**: User can log in with email/password and receive a JWT
- [ ] **AUTH-02**: Protected endpoints validate the JWT and reject unauthenticated requests
- [ ] **AUTH-03**: System exposes a `/health` endpoint reporting service status

### Talents

- [ ] **TAL-01**: System stores the talent catalog in the database (21 initial talents), addable/editable without code changes
- [ ] **TAL-02**: Each talent maps to one or more Pipedrive products for revenue attribution

### Pipedrive (M2)

- [ ] **PIPE-01**: System syncs Pipedrive deals (stages, value, products, custom fields) into local SQLite on a schedule + manual "sync now"
- [ ] **PIPE-02**: System maps deal product → talent and computes 70% fixed commission per deal
- [ ] **PIPE-03**: System classifies deals with $0 MXN as "Sin cotizar"
- [ ] **PIPE-04**: System captures custom fields: razón de pérdida, categoría de marca, fecha de cobro esperada
- [ ] **PIPE-05**: System tracks the 6 funnel stages (Llamada → Cotización → Negociación → Contrato → En ejecución → Cobranza) per deal

### Google Sheets (M3)

- [ ] **SHEET-01**: System syncs leads from a Google Sheet (fed by Gmail) into local SQLite
- [ ] **SHEET-02**: Leads are classified by talent, source, and status

### Trello (M4)

- [ ] **TRELLO-01**: System syncs Trello cards for deals with signed contracts, distinguishing "en ejecución" vs "en cobranza"
- [ ] **TRELLO-02**: Trello cards display expected collection dates
- [ ] **TRELLO-03**: Automation — when a Pipedrive deal is marked "ganado", system creates a Trello card with the expected collection date

### Dashboard

- [ ] **DASH-01**: Resumen ejecutivo — global KPIs, talent ranking by revenue, AI-generated insights, recent activity feed
- [ ] **DASH-02**: Por talento — KPIs, monthly revenue projection (cobrado/proyección/pendiente as stacked bars), collection calendar, individual funnel, lost opportunities, brand category breakdown, top 3 campaigns of the month, full campaign table (campaign/status/amount)
- [ ] **DASH-03**: Funnel completo — 6 stages with deal count and amount, bottleneck detection
- [ ] **DASH-04**: Leads Gmail — leads classified by talent, source, and status
- [ ] **DASH-05**: Reportes — UI to generate AI PDF reports and browse/download report history

### AI Reports & Agent (M5-M6)

- [ ] **REPORT-01**: System generates a monthly PDF report per talent (or all talents) using Claude AI — all financial figures computed in Python, Claude only narrates
- [ ] **REPORT-02**: User can download historical generated reports
- [ ] **AGENT-01**: User can query dashboard data via an embedded natural-language agent (read-only, no write actions)

### Deploy (M7)

- [ ] **DEPLOY-01**: System runs in Docker with a Dockerfile + docker-compose.yml
- [ ] **DEPLOY-02**: System deploys to EasyPanel with a persistent volume for the SQLite database (verified to survive redeploys)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Future Enhancements

- **FUT-01**: Real-time sync via Pipedrive/Trello webhooks (replacing polling)
- **FUT-02**: Threshold-based alerts (e.g., deals stalled >14 days)
- **FUT-03**: Role-based access control (dirección vs equipo comercial vs por-talento)
- **FUT-04**: "OpenClaw" multi-agent orchestration extensions (prospección, WhatsApp, contratos)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Roles de usuario diferenciados | Equipo pequeño; mismo acceso para todos por ahora (ver FUT-03) |
| Multi-tenant / soporte multi-agencia | Diseño específico para SEG, aunque modular |
| Construir M1-M7 simultáneamente | Desarrollo incremental, M1 primero |
| Sync en tiempo real (webhooks) | Polling es suficiente para esta escala (ver FUT-01) |
| ML-based revenue forecasting | Proyección determinística/heurística es suficiente |
| Agente IA con acciones de escritura autónomas | Agente de M6 es de solo lectura por seguridad de datos |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | TBD | Pending |
| AUTH-02 | TBD | Pending |
| AUTH-03 | TBD | Pending |
| TAL-01 | TBD | Pending |
| TAL-02 | TBD | Pending |
| PIPE-01 | TBD | Pending |
| PIPE-02 | TBD | Pending |
| PIPE-03 | TBD | Pending |
| PIPE-04 | TBD | Pending |
| PIPE-05 | TBD | Pending |
| SHEET-01 | TBD | Pending |
| SHEET-02 | TBD | Pending |
| TRELLO-01 | TBD | Pending |
| TRELLO-02 | TBD | Pending |
| TRELLO-03 | TBD | Pending |
| DASH-01 | TBD | Pending |
| DASH-02 | TBD | Pending |
| DASH-03 | TBD | Pending |
| DASH-04 | TBD | Pending |
| DASH-05 | TBD | Pending |
| REPORT-01 | TBD | Pending |
| REPORT-02 | TBD | Pending |
| AGENT-01 | TBD | Pending |
| DEPLOY-01 | TBD | Pending |
| DEPLOY-02 | TBD | Pending |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 25 ⚠️ (will be resolved by roadmap creation)

---
*Requirements defined: 2026-06-09*
*Last updated: 2026-06-09 after initial definition*
