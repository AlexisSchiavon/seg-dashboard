# Feature Research

**Domain:** Commercial/sales intelligence dashboard for a talent/influencer management agency (consolidates CRM funnel, lead inbox, and campaign execution/collections; AI reporting + NL query agent)
**Researched:** 2026-06-09
**Confidence:** MEDIUM-HIGH (table stakes verified across multiple CRM-analytics and influencer-CRM sources; AI-agent patterns are an emerging category — MEDIUM confidence on specifics)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist in any sales/pipeline analytics dashboard or talent-revenue tool. Missing these makes the product feel like "just another spreadsheet."

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Global KPI summary (total pipeline value, won revenue, active deals, conversion rate) | Every CRM-analytics dashboard leads with top-line numbers; this is the "at a glance" health check execs open first | LOW | Already in PROJECT.md scope (Resumen ejecutivo). Pure aggregation over Pipedrive deals. |
| Funnel/pipeline stage view with deal count + value per stage | Standard sales pipeline visualization (Coupler.io, monday.com, Salesforce all lead with this) — funnel-shaped or kanban-style stage breakdown | LOW-MEDIUM | 6 stages already defined (Llamada → Cotización → Negociación → Contrato → En ejecución → Cobranza). Pull stage + deal value from Pipedrive. |
| Stage conversion rates (% advancing stage-to-stage) | Core metric across all pipeline analytics tools — reveals where deals fall off | MEDIUM | Requires historical stage-transition data or snapshot-based calc. Pipedrive API exposes current stage; conversion rate needs either deal-history endpoint or periodic snapshots stored in SQLite. |
| Bottleneck detection (stage with abnormal stall/drop-off) | Explicitly requested in PROJECT.md ("detección de cuellos de botella"); standard in pipeline-analysis tools (onpipeline, Breadcrumbs, DealHub) | MEDIUM | Simple version: flag stage with lowest conversion % or longest avg time-in-stage. Doesn't need ML — threshold/heuristic is sufficient and expected. |
| Per-account/per-talent revenue ranking | Analogous to per-rep leaderboards (standard in sales scorecards) — agency owner wants to know which talents drive revenue | LOW | Sort talents by won revenue (70% commission) over period. Direct aggregation. |
| Per-talent KPI card (revenue, deal count, win rate) | Sales rep scorecards universally include win rate, deal size, deal count — same pattern applies per talent | LOW-MEDIUM | "Win rate" = won deals / (won + lost) for that talent's deals. |
| Per-talent funnel (mini funnel scoped to one talent) | Drill-down from global to individual is standard UX in CRM analytics (global dashboard → entity-level dashboard) | LOW | Same funnel logic as global, filtered by talent (Pipedrive product field). |
| Lost-opportunity tracking with loss reason | Loss-reason analysis is standard in pipeline health tools; agency already captures this in Pipedrive custom fields | LOW-MEDIUM | 5 predefined reasons already exist. Aggregate by reason, by talent, by brand category. |
| Lead source / channel classification | "Define a consistent lead source classification before implementation... categories must be mutually exclusive" — standard lead-analytics requirement | LOW-MEDIUM | Gmail leads already classified by talent/source/status in Sheets — just needs ingestion + display, no new classification logic for v1. |
| Revenue projection / forecast (collected vs. projected vs. pending) | "Cash collections forecasting" using promised payment dates is standard AR practice; explicitly requested per-talent | MEDIUM-HIGH | Requires combining Pipedrive "fecha de cobro esperada" custom field + Trello collection-stage cards. This is the most data-integration-heavy table-stakes feature. |
| Collection calendar (upcoming payment dates) | Direct analog to AR collections dashboards showing "clients with payment-promised dates and amounts" | MEDIUM | Pulls from Trello cards in "cobranza" stage + Pipedrive expected-payment-date field. |
| Brand category breakdown (industry segmentation of clients) | Standard segmentation dimension in CRM analytics — "which verticals are we winning in" | LOW | 6 categories already defined as Pipedrive custom field; simple grouping/aggregation. |
| Recent activity feed | Common executive-dashboard element — "what changed recently" without manual digging | LOW-MEDIUM | Could be derived from Pipedrive deal updates + Trello card moves; needs polling/webhook strategy. |
| Top campaigns / top deals list (per talent and global) | "Top performers" lists are universal in scorecards and revenue dashboards | LOW | Sort deals by value, filter won/active. |
| Full sortable/filterable data table (all campaigns/deals) | Power users always want the underlying table beneath the visualizations — non-negotiable in B2B dashboards | LOW-MEDIUM | Standard table component; filter by talent, stage, date, status. |
| Authentication (login-gated dashboard) | Internal commercial data — baseline expectation for any business dashboard | LOW | Already scoped as M1 (JWT). |
| Mobile-responsive / dark mode UI | Already validated via mockup; agency staff likely check on phone | LOW | Already designed; just needs backend wiring. |

### Differentiators (Competitive Advantage)

Features that set this product apart from generic CRM dashboards or off-the-shelf influencer-CRM tools (CreatorIQ, GRIN, Klear, etc.) — these are not expected by default but deliver the "wow, this replaced 3 tools and a spreadsheet" value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Cross-source data consolidation (Pipedrive + Sheets + Trello in one view) | This IS the core value proposition per PROJECT.md — no off-the-shelf influencer CRM unifies a Mexican agency's exact stack (Pipedrive funnel + Gmail-lead spreadsheet + Trello execution/collections board) | HIGH | The hard engineering problem of the whole project. Each integration is its own milestone (M2-M4). |
| AI-generated monthly PDF reports (Claude) | "AI client reporting dashboards" are an emerging 2026 category (matzanalytics) but mostly for marketing agencies reporting to external clients — applying this internally for an owner/exec audience with talent-specific narrative insights is differentiated | MEDIUM-HIGH | Needs a report-template + data-aggregation service feeding Claude a structured prompt; PDF rendering (e.g., WeasyPrint/ReportLab). Depends on KPI/funnel services being stable first. |
| Embedded natural-language query agent over consolidated data | "Agentic BI" / "chat with your data" is the cutting edge of 2026 BI tooling (GoodData, Powerdrill Bloom) — embedding this directly in an agency's internal tool (vs. buying Tableau/Domo) is a meaningful differentiator and fits the "OpenClaw" multi-agent vision | HIGH | Requires a semantic layer (defined metrics/entities) so Claude doesn't hallucinate against raw SQL. Should query pre-aggregated views/services, not raw tables, per "governed semantic layer" best practice found in research. |
| AI-generated narrative insights on Resumen Ejecutivo (e.g., "Talento X subió 40% vs. mes anterior, oportunidad: cerrar 3 deals en Cotización") | Goes beyond static anomaly-threshold alerts — plain-language insight generation is what separates "AI dashboards" from regular BI in 2026 sources | MEDIUM | Can reuse the same Claude integration as PDF reports; lower-stakes than full NL agent (pre-computed insight generation vs. open-ended Q&A). |
| Automated Pipedrive→Trello handoff (deal won → collection card auto-created) | Removes a manual step explicitly named in PROJECT.md; most influencer-CRM tools don't bridge a CRM and a kanban execution board this way | MEDIUM | Requires Pipedrive webhook (or polling) → Trello API card creation with collection date pre-filled. |
| Talent catalog as data/config (no-code talent onboarding) | Generic CRM tools require admin-level config changes to add a "rep" or "account"; here it's designed as simple data entry, supporting agency growth (21 → N talents) | LOW-MEDIUM | DB table + simple admin form/endpoint. Foundational — should land early (M1/M2) since Pipedrive product mapping depends on it. |
| Modular architecture for future multi-agent extensions ("OpenClaw") | Not a user-facing feature today, but a structural differentiator vs. monolithic dashboards — positions the codebase for prospecting/WhatsApp/contract agents later | MEDIUM | Architectural discipline (clean service boundaries in `services/`), not a discrete feature — affects ARCHITECTURE.md more than FEATURES.md. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem valuable but would create disproportionate complexity, scope creep, or risk for this project's context (small internal team, single agency, incremental build).

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Real-time / live-sync dashboard (sub-minute updates from Pipedrive/Trello/Sheets) | "Real-time visibility" sounds like the obvious goal of a consolidation dashboard | Webhooks + real-time sync across 3 external APIs (rate limits, auth, retries) adds major complexity for a tool checked a few times a day by a small team; "real-time" is rarely actually needed for monthly/weekly revenue tracking | Scheduled sync (e.g., every 15-30 min via cron/background job) or on-demand refresh button. Revisit only if usage patterns show staleness is a real pain point. |
| Role-based access control / granular permissions | Common "best practice" CRM feature; tempting to build "properly" from day one | PROJECT.md explicitly scopes this OUT — small team, everyone sees the same data; building RBAC now is premature complexity that slows M1 | Single authenticated user tier for now (already decided). Add RBAC only if team grows or external stakeholders (talents themselves) get access later. |
| Multi-tenant / multi-agency support | "Why not make it sellable to other agencies?" is a tempting expansion thought | PROJECT.md explicitly scopes this OUT — designing for multi-tenancy now (tenant isolation, configurable funnel stages per tenant, etc.) would significantly complicate the data model and auth for zero near-term benefit | Build single-tenant, but keep config (talent catalog, funnel stages, brand categories) in DB/config rather than hardcoded — gets "modularity" benefit without multi-tenant complexity. |
| Open-ended NL agent with full database write access / autonomous actions | "Agentic BI" trend suggests agents that "execute multi-step workflows without requiring the user to touch the interface" | Letting an LLM agent autonomously modify Pipedrive deals, Trello cards, or send communications is a high-risk surface (hallucinated actions, irreversible CRM changes) for v1 | M6 NL agent should be read-only (query/insight generation against the semantic layer). Any write-actions (e.g., "create a Trello card") should be a separate, explicitly-confirmed action — not autonomous. |
| Predictive ML revenue forecasting (regression/ML models on historical deal data) | "AI-powered forecasting" is marketed heavily by enterprise tools (Salesforce Einstein, etc.) | With ~21 talents and a modest deal volume, there isn't enough historical data for a meaningful ML model; building one adds complexity without statistical validity | Use deterministic projection: sum of (won/collected) + (weighted pipeline value by stage probability) + (Trello collection-stage amounts with dates). This is what "revenue projection" already implies in PROJECT.md and matches AR-forecasting best practice (DSO-based, not ML-based). |
| General-purpose BI tool replacement (custom dashboard builder, drag-and-drop widgets) | "What if users want to build their own views?" | Massive scope increase; this is a purpose-built dashboard for a specific agency's specific funnel, not a BI platform | Fixed, well-designed dashboard sections (already specified: Resumen, Por Talento, Funnel, Leads, Reportes). If new views are needed later, add them as new sections deliberately. |
| Full bi-directional sync (dashboard writes back to Pipedrive/Trello/Sheets beyond the one defined automation) | Seems natural once you're "integrated" with these tools | Bi-directional sync risks data conflicts, requires careful conflict resolution, and turns a read-mostly dashboard into a system of record competing with the existing tools | Dashboard remains primarily read/aggregate. The one explicitly-scoped automation (Pipedrive won → Trello collection card) is a narrow, one-directional, well-defined trigger — not general sync. |
| Real-time anomaly-detection ML (statistical outlier models on every metric) | "AI watches metrics and flags unusual movement" sounds impressive | Overkill for ~21 talents and monthly cadence; threshold-based heuristics (e.g., "no movement in stage X for 14 days," "talent revenue down >30% MoM") achieve the same practical value with far less engineering | Simple rule-based flags computed in `services/kpis.py` / `services/funnel.py`, surfaced as "insights" — optionally narrated by Claude for the AI-insights differentiator. |

## Feature Dependencies

```
Talent catalog (DB/config)
    └──requires──> [foundational, before everything]

Pipedrive integration (deals, stages, custom fields)
    └──requires──> Talent catalog (product=talent mapping)
    └──enables──> Global KPI summary
    └──enables──> Funnel view (6 stages)
    └──enables──> Per-talent KPIs & funnel
    └──enables──> Lost-opportunity tracking
    └──enables──> Brand category breakdown
    └──enables──> Revenue projection (Pipedrive portion)

Funnel view (6 stages)
    └──requires──> Pipedrive integration
    └──enables──> Stage conversion rates
                       └──enables──> Bottleneck detection

Google Sheets integration (Gmail leads)
    └──requires──> Talent catalog (lead-to-talent classification)
    └──enables──> Lead source/channel classification dashboard

Trello integration (campaign execution + collections)
    └──requires──> Talent catalog
    └──enhances──> Revenue projection (collection calendar dates)
    └──enables──> Collection calendar
    └──enables──> "En ejecución" vs "en cobranza" distinction

Pipedrive→Trello automation (won deal → collection card)
    └──requires──> Pipedrive integration + Trello integration (both)

Revenue projection (collected/projected/pending)
    └──requires──> Pipedrive integration (expected payment date field)
    └──requires──> Trello integration (collection-stage cards)
    └──enhances──> Per-talent view, Resumen Ejecutivo

KPI/funnel/insight services (services/kpis.py, funnel.py)
    └──requires──> Pipedrive integration (minimum)
    └──enables──> AI-generated narrative insights (Resumen Ejecutivo)
    └──enables──> AI-generated PDF reports (M5)
    └──enables──> NL query agent semantic layer (M6)

AI-generated PDF reports (M5)
    └──requires──> KPI/funnel/insight services stable
    └──requires──> Anthropic Claude API integration

NL query agent (M6)
    └──requires──> KPI/funnel/insight services stable (semantic layer / read-only data access)
    └──requires──> Anthropic Claude API integration
    └──conflicts with──> Open-ended autonomous write-actions (anti-feature; should remain read-only)

Recent activity feed
    └──requires──> Pipedrive integration + Trello integration (at minimum one)
    └──benefits from──> Polling/sync strategy decision (real-time vs scheduled)
```

### Dependency Notes

- **Talent catalog must come first (or alongside M1/M2):** Every other integration maps external data (Pipedrive products, Sheet rows, Trello cards) to a talent. If the catalog isn't data-driven from the start, adding talent #22 later requires touching integration code — directly conflicting with the "extensibilidad" constraint in PROJECT.md.
- **Funnel view requires Pipedrive before bottleneck detection can exist:** Conversion rates and bottleneck flags are derived metrics on top of the raw funnel data — can't be built or even meaningfully designed until M2 ships.
- **Revenue projection is the highest-dependency feature:** It's the only feature that genuinely needs both Pipedrive (M2) AND Trello (M4) data simultaneously. This suggests the "Por Talento" revenue projection sub-feature may need to ship in two passes — a Pipedrive-only approximation after M2, refined with collection-calendar accuracy after M4.
- **AI features (M5/M6) depend on stable services, not raw integrations:** Both the PDF reports and the NL agent should be built against `services/kpis.py`, `services/funnel.py`, etc. — not directly against Pipedrive/Trello/Sheets clients. This is both a dependency ordering point (M5/M6 come after M2-M4) and an architecture decision (semantic layer / governed metrics layer, per 2026 agentic-BI best practice).
- **NL agent conflicts with autonomous write-actions:** The dependency chain explicitly excludes write-back capability. If a future "OpenClaw" agent needs to take actions (create Trello cards, update Pipedrive deals), that should be a distinct, explicitly-scoped capability with its own confirmation UX — not bundled into M6's read-only query agent.
- **Recent activity feed is the most "optional/deferrable" table-stakes item:** It's listed as expected by PROJECT.md's Resumen Ejecutivo, but technically depends on a sync/polling strategy decision that doesn't need to be made until M2-M4 are functional. Could ship as "last updated" + simple log initially.

## MVP Definition

### Launch With (v1 — through M2, "Pipedrive-only dashboard")

Minimum viable product — what's needed to validate that consolidation + funnel visibility delivers value, before adding more data sources.

- [ ] Talent catalog (DB-backed, admin-addable) — foundational dependency for everything else
- [ ] Authentication (JWT) + health check — already scoped M1
- [ ] Global KPI summary (pipeline value, won revenue, deal counts, conversion rate) — the headline number execs check first
- [ ] Funnel view: 6 stages with deal count + value — core visualization, validates Pipedrive integration end-to-end
- [ ] Per-talent revenue ranking — directly answers "who's our top earner this month," the question that currently requires manual Pipedrive review
- [ ] Per-talent KPI card + mini funnel — proves the "drill down per talent" pattern works
- [ ] Lost-opportunity tracking with loss reason (per talent + global) — high value, low cost, data already in Pipedrive

### Add After Validation (v1.x — M3-M4, "full data consolidation")

Features to add once the Pipedrive-only core proves the consolidation concept works.

- [ ] Gmail leads dashboard (classified by talent/source/status) — trigger: M3 Sheets integration ships
- [ ] Stage conversion rates + bottleneck detection — trigger: enough Pipedrive history accumulated to compute meaningful stage-to-stage rates (may need a few weeks of snapshot data post-M2)
- [ ] Collection calendar — trigger: M4 Trello integration ships
- [ ] Revenue projection (collected/projected/pending) — trigger: M4 ships, since accurate projection needs Trello collection dates
- [ ] Brand category breakdown — trigger: low effort, can ship as soon as the field is reliably populated in Pipedrive (likely alongside M2 but lower priority than core funnel)
- [ ] Top 3 campaigns + full campaign table (per talent) — trigger: natural extension once per-talent view (v1) + Trello execution data (M4) both exist
- [ ] Pipedrive→Trello automation (won deal → collection card) — trigger: M4 ships and collection workflow is validated manually first
- [ ] Recent activity feed — trigger: once a sync/polling cadence is settled across M2-M4

### Future Consideration (v2+ — M5-M6 and beyond)

Features to defer until the core consolidated dashboard (data + funnel + per-talent views) is in daily use and validated.

- [ ] AI-generated monthly PDF reports — defer until KPI/funnel services are stable and the metrics they'd narrate are trustworthy (garbage in, garbage out for AI narratives)
- [ ] AI-generated narrative insights on Resumen Ejecutivo — defer alongside/after PDF reports; reuses same Claude integration
- [ ] Embedded NL query agent — defer until a semantic layer (defined metrics across all 3 sources) exists; building this against unstable/raw data sources risks a poor first impression of the "AI agent" feature
- [ ] Threshold-based "alerts" (e.g., "Talento X sin actividad 14 días") — nice-to-have layered on top of activity feed + KPI services, low urgency
- [ ] Modular multi-agent extensions ("OpenClaw" prospecting/WhatsApp/contract agents) — explicitly future vision, not part of this dashboard's roadmap

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Talent catalog (data-driven) | HIGH | LOW | P1 |
| Global KPI summary | HIGH | LOW | P1 |
| Funnel view (6 stages) | HIGH | MEDIUM | P1 |
| Per-talent KPIs + mini funnel | HIGH | MEDIUM | P1 |
| Per-talent revenue ranking | HIGH | LOW | P1 |
| Lost-opportunity tracking (loss reasons) | MEDIUM | LOW | P1 |
| Gmail leads dashboard | MEDIUM | MEDIUM | P2 |
| Stage conversion rates + bottleneck detection | HIGH | MEDIUM | P2 |
| Collection calendar | HIGH | MEDIUM | P2 |
| Revenue projection (collected/projected/pending) | HIGH | HIGH | P2 |
| Brand category breakdown | LOW-MEDIUM | LOW | P2 |
| Top campaigns + full campaign table | MEDIUM | MEDIUM | P2 |
| Pipedrive→Trello automation | MEDIUM | MEDIUM | P2 |
| Recent activity feed | MEDIUM | MEDIUM | P3 |
| AI-generated PDF reports | HIGH (strategic) | HIGH | P3 |
| AI narrative insights | MEDIUM | MEDIUM | P3 |
| Embedded NL query agent | HIGH (strategic) | HIGH | P3 |
| Read-only NL agent constraint | HIGH (risk mitigation) | LOW | P1 (when M6 starts) |

**Priority key:**
- P1: Must have for launch (M1-M2 dashboard validates the core "Pipedrive consolidation" thesis)
- P2: Should have, add when possible (M3-M4 complete the data-source consolidation)
- P3: Nice to have, future consideration (M5-M6 add the AI-differentiation layer)

## Competitor Feature Analysis

| Feature | Influencer CRM platforms (CreatorIQ, GRIN, Klear, Influencity, CreatorsJet) | Generic sales pipeline dashboards (Salesforce, HubSpot, Pipedrive native reports, monday.com) | Our Approach |
|---------|------|------|--------------|
| Pipeline/funnel visualization with stage conversion | Limited — these tools focus on campaign/creator discovery, not a sales funnel; conversion tracking is for affiliate links/discount codes, not deal stages | Core feature — every tool has this | Adopt the generic pipeline-dashboard pattern (funnel + conversion + bottleneck), since SEG's "product" is a B2B sales process (brand deals), not creator discovery |
| Per-creator/per-account revenue attribution | Core feature — "revenue attribution... see exactly who's driving conversions," but framed around affiliate/UTM tracking for brand campaigns | Per-rep performance scorecards (win rate, quota, deal size) | Closer to the generic CRM pattern: per-talent = per-"account owner" in a B2B sense, ranked by closed revenue and win rate, not by audience-driven conversions |
| Multi-source consolidation (CRM + spreadsheet + kanban) | Not a focus — these platforms are themselves the system of record, not aggregators of 3rd-party tools | Some BI tools (Coupler.io) connect multiple CRMs, but not spreadsheet+kanban+CRM in one custom view | This is SEG's unique need — no off-the-shelf product does Pipedrive+Sheets+Trello consolidation for a talent agency's specific workflow; build custom (this is the core differentiator) |
| AI reporting (PDF/narrative) | Emerging in 2026 ("AI client reporting dashboards" for marketing agencies reporting to brand clients) | Emerging — Domo, Zoho Analytics, Powerdrill Bloom adding NL/AI report features | Build internal-facing AI reports (owner/exec audience) using Claude, narrower scope than general-purpose AI BI tools — feasible because data model is small and well-understood |
| Embedded NL query agent | Not present in influencer-CRM category | Present in 2026 enterprise BI (Tableau Pulse, Domo, GoodData "agentic analytics") but typically requires expensive platform subscriptions | Build a lightweight, read-only version scoped to SEG's semantic layer — avoids both the cost of enterprise BI platforms and the need to migrate off Pipedrive/Trello/Sheets |
| Collections/AR tracking tied to campaign execution | Not present — influencer CRMs track campaign deliverables, not invoicing/collections | Generic CRMs have some AR/invoicing add-ons but not native to pipeline dashboards | Build custom: Trello "cobranza" stage + Pipedrive expected-payment-date field is SEG's actual AR system; dashboard surfaces it, doesn't replace it |

## Sources

- [Sales Pipeline Dashboard Examples & Reporting Templates | Coupler.io](https://www.coupler.io/dashboard-examples/sales-pipeline-dashboard)
- [Sales Pipeline Analysis: Complete Guide to Pipeline Health & Optimization | CaptivateIQ](https://www.captivateiq.com/blog/sales-pipeline-analysis)
- [How to Find and Overcome Sales Pipeline Bottlenecks | OnPipeline](https://www.onpipeline.com/crm-sales/sales-pipeline-bottlenecks-find-and-overcome/)
- [Sales Pipeline Analysis: Use These 5 Analytics to Identify Bottlenecks | Breadcrumbs](https://breadcrumbs.io/blog/sales-pipeline-analysis/)
- [Sales dashboard templates: 11 proven examples for 2026 | monday.com](https://monday.com/blog/crm-and-sales/sales-dashboard-templates/)
- [Influencer CRM for Agencies & Talent Managers | CreatorsJet](https://www.creatorsjet.com/influencer-crm)
- [Top 13 Influencer CRM Software for Managing Creator Relationships | Influencer Hero](https://www.influencer-hero.com/blogs/top-influencer-crm-software)
- [Influencer CRM Platforms 2025 | influencers-time.com](https://www.influencers-time.com/top-influencer-crm-platforms-and-features-to-boost-roi-in-2025/)
- [Forecasting Accounts Receivable: How Automation Can Improve the Process | Invoiced](https://www.invoiced.com/resources/blog/forecasting-accounts-receivable)
- [Short-Term Accounts Receivable Collections Forecasting | Gaviti](https://gaviti.com/how-to-improve-short-term-accounts-receivable-collections-forecasting/)
- [Lead Source Attribution | LeadSources.io](https://leadsources.io/glossary/lead-source-attribution)
- [Lead analytics dashboard: 7 metrics every sales team needs in 2026 | monday.com](https://monday.com/blog/crm-and-sales/lead-analytics-dashboard/)
- [Build the Perfect Sales Rep Scorecard | GoodData](https://www.gooddata.com/blog/build-perfect-sales-rep-scorecard/)
- [9 Sales KPIs Every Sales Team Should Be Tracking | Salesforce](https://www.salesforce.com/sales/performance-management/sales-kpis/)
- [AI Client Reporting Dashboard: 2026 Agency Buyer's Guide | Matz Analytics](https://www.matzanalytics.com/post/ai-client-reporting-dashboard-2026-guide)
- [Agentic Analytics: The Complete Guide to AI-Driven Data Intelligence | GoodData.AI](https://www.gooddata.ai/blog/agentic-analytics-complete-guide-to-ai-driven-data-intelligence/)
- [What Is Agentic BI? How AI Agents Are Replacing Dashboards | Knowi](https://www.knowi.com/blog/what-is-agentic-bi/)
- [AI in Analytics: Anomaly Detection, Predictions, and Automated Insights | Kissmetrics](https://www.kissmetrics.io/blog/ai-analytics-anomaly-detection-guide)
- Project context: `.planning/PROJECT.md` (SEG Talent Intelligence Dashboard requirements, business logic, mockup reference)

---
*Feature research for: Commercial intelligence dashboard for talent/influencer management agency (SEG Talent Intelligence Dashboard)*
*Researched: 2026-06-09*
