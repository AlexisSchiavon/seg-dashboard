# Project Research Summary

**Project:** SEG Talent Intelligence Dashboard
**Domain:** Commercial/sales intelligence dashboard for a talent-management agency — multi-source data consolidation (Pipedrive CRM + Google Sheets leads + Trello execution/collections) with FastAPI backend, JWT auth, SQLite, and Claude-powered AI reporting/agent layer
**Researched:** 2026-06-09
**Confidence:** HIGH

## Executive Summary

This is a modular FastAPI monolith whose core value proposition is consolidating three disconnected tools (Pipedrive sales pipeline, a Gmail-fed Google Sheet of leads, and a Trello execution/collections board) into a single internal dashboard for a talent agency, plus an AI layer (Claude) for narrative reports and a read-only natural-language query agent. Experts build this kind of system as a layered architecture — `routers/` -> `services/` -> `integrations/` -> `sync/` (scheduled) -> SQLite — where the dashboard always reads from a local synced cache, never from live external APIs on page load. The recommended stack (FastAPI + SQLAlchemy 2.0 + SQLite/WAL + PyJWT + pwdlib[argon2] + httpx-based thin integration wrappers + WeasyPrint/Jinja2 for PDFs + Anthropic SDK) is current, well-supported, and avoids several recently-broken "classic tutorial" dependencies (passlib, python-jose, py-trello).

The recommended approach is strictly sequential and dependency-driven: establish auth, DB schema (including a data-driven `talents` table from day one), and SQLite WAL/persistence conventions in M1; build Pipedrive integration with pagination and custom-field-key resolution in M2 (this unlocks the global KPI summary, funnel view, per-talent views, and lost-opportunity tracking — the MVP core); add Sheets (M3) and Trello (M4) as additive sync sources following the same adapter+sync pattern; then layer AI reports (M5) and a read-only NL agent (M6) on top of stable services, with a hard "Claude narrates, code computes" rule to prevent hallucinated financial figures; finally Dockerize/deploy to EasyPanel (M7) with a tested persistent volume for SQLite.

Key risks: (1) foundational auth library breakage on Python 3.12 (passlib/bcrypt incompatibilities) if the classic FastAPI tutorial is followed verbatim — mitigated by using PyJWT + pwdlib[argon2] from the start; (2) SQLite "database is locked" errors once background sync jobs (M2+) write concurrently with dashboard reads — mitigated by enabling WAL mode + busy_timeout in M1's `database.py`; (3) silent data-correctness bugs from Pipedrive's hashed custom-field keys and missing pagination, and from Google Sheets schema drift — both addressed by adapter-layer normalization and header-based/mapped field access established in M2/M3; (4) AI-generated reports presenting hallucinated numbers — addressed by a strict compute-in-Python/narrate-with-Claude separation; (5) SQLite data loss on EasyPanel redeploy — addressed by an explicit persistent-volume convention decided in M1 and verified in M7.

## Key Findings

### Recommended Stack

The stack is largely fixed by project constraints (Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite, httpx, python-dotenv) and research confirms no compatibility blockers. The most actionable findings are in the supporting libraries: avoid `python-jose` and `passlib` (both unmaintained and broken on current Python/bcrypt versions) in favor of `PyJWT` + `pwdlib[argon2]`; avoid third-party Pipedrive/Trello SDKs (none are well-maintained) in favor of thin typed `httpx` wrappers in `app/integrations/`; use `gspread` + `google-auth` with service-account auth for Sheets (no OAuth flow needed); and for AI reports, generate structured content with Claude, render via Jinja2 + WeasyPrint to PDF (WeasyPrint requires system libs — Pango/Cairo/GDK-Pixbuf — budget for this in the M7 Dockerfile).

**Core technologies:**
- FastAPI 0.115-0.137 + Uvicorn[standard] — web framework/ASGI server, maps cleanly to routers/services structure
- SQLAlchemy 2.0 (typed `Mapped`/`mapped_column`) + Alembic — ORM and migrations, sync engine (simplest for SQLite + Alembic)
- PyJWT + pwdlib[argon2] — JWT and password hashing; explicitly NOT python-jose/passlib (broken on current Python/bcrypt)
- httpx — universal HTTP client for all integrations (Pipedrive, Trello, raw REST), sync `httpx.Client` for M1-M4
- gspread + google-auth — Google Sheets via service account (M3)
- anthropic SDK + WeasyPrint + Jinja2 — Claude reports (M5) and NL agent tool-use (M6)

### Expected Features

**Must have (table stakes — v1/MVP through M2):**
- Talent catalog as DB-backed config (foundational for everything else)
- Global KPI summary (pipeline value, won revenue, deal counts, conversion rate)
- Funnel view (6 stages: Llamada -> Cotizacion -> Negociacion -> Contrato -> En ejecucion -> Cobranza) with deal count + value
- Per-talent revenue ranking, KPI card, and mini funnel
- Lost-opportunity tracking with loss reason
- Authentication (JWT) + health check, mobile-responsive dark UI (already designed)

**Should have (differentiators — v1.x, M3-M4):**
- Cross-source consolidation (Pipedrive + Sheets + Trello) — the core engineering differentiator, no off-the-shelf tool does this
- Gmail leads dashboard (M3), collection calendar + revenue projection (collected/projected/pending) requiring both Pipedrive and Trello (M4)
- Stage conversion rates + bottleneck detection
- Pipedrive->Trello automation (won deal -> collection card) with reconciliation

**Defer (v2+, M5-M6):**
- AI-generated monthly PDF reports and narrative insights (after KPI/funnel services are stable)
- Embedded read-only NL query agent over a governed semantic layer
- Threshold-based alerts, "OpenClaw" multi-agent extensions

**Anti-features explicitly excluded:** real-time/webhook sync (use polling, defer webhooks to post-M7), RBAC, multi-tenancy, autonomous/write-capable AI agent actions, ML-based forecasting (use deterministic projection instead), general-purpose BI builder, full bi-directional sync.

### Architecture Approach

A modular FastAPI monolith with strict layering: `routers/` (HTTP boundary, auth + validation) -> `services/` (business logic: funnel math, KPI aggregation, report/agent orchestration — talent-agnostic, DB-driven) -> `integrations/` (one adapter class per external API, returns normalized Pydantic/dataclass models, never raw JSON, no business logic) -> `sync/` (new module, scheduled APScheduler jobs that upsert normalized data into SQLite) -> `models.py`/`database.py` (SQLAlchemy 2.0, SQLite with WAL mode). Dashboard reads always come from the local SQLite cache, never live external calls — sync runs on a 15-30 min interval plus an on-demand "Sync now" button.

**Major components:**
1. `auth/` (M1, self-contained package: security, dependencies, router) — built once, reused unchanged through M2-M7 via `Depends(get_current_user)`
2. `integrations/` (pipedrive.py, sheets.py, trello.py, claude.py) — adapter+normalization pattern, each independently testable
3. `sync/` (scheduler.py + jobs.py + SyncLog table) — stateful orchestration layer separate from stateless integrations, extended additively M2->M3->M4
4. `services/` (funnel.py, kpis.py, reports.py, agent.py) — single source of truth for business logic (70% commission calc, funnel/bottleneck logic), consumed by both routers and AI features
5. `models.py`/`database.py` — `Talent` table with nullable per-provider mapping columns (pipedrive_product_id, sheets_tag, trello_label_id), SQLite WAL mode from M1

### Critical Pitfalls

1. **bcrypt/passlib breakage on Python 3.12** — the classic FastAPI auth tutorial is currently broken; use PyJWT + pwdlib[argon2] from M1, verify hash/verify roundtrip with a test before building on it.
2. **SQLite "database is locked" once sync jobs (M2+) write concurrently with dashboard reads** — enable `PRAGMA journal_mode=WAL` + `busy_timeout=10000` in `database.py` from M1, before any other module is built on it.
3. **Pipedrive custom fields referenced by hashed key, not label** — resolve name->key mapping via the `dealFields` endpoint at startup/cache; build this into the M2 Pipedrive client from day one, with an integration test asserting non-null values for loss reason/brand category/collection date.
4. **Talent catalog hardcoded instead of DB-driven** — define a `talents` table in M1 (even before populated), seeded with the 21 current talents; every later module references talents by internal ID, satisfying "add talents without touching code."
5. **Claude-hallucinated numbers in AI reports/agent (M5/M6)** — hard architectural rule: all numeric aggregates computed in Python (`services/kpis.py`/`funnel.py`), Claude only narrates pre-computed numbers; NL agent uses tool-calling against real queries, never reasons over raw dumps.

Additional notable pitfalls: SQLite data loss on EasyPanel redeploy without a persistent volume (M7, but path convention decided in M1); Pipedrive pagination/2000-result cap silently truncating KPI totals (M2); Trello automation needing a reconciliation job, not just a webhook (M4); Google Sheets schema drift and quota exhaustion — use `get_all_records()` and sync-to-DB pattern (M3); Claude API cost runaway without prompt caching (M5/M6).

## Implications for Roadmap

Based on research, suggested phase structure (aligned with the M1-M7 milestones already implied by PROJECT.md):

### Phase 1: Foundation — Auth, DB Schema, Health Check (M1)
**Rationale:** Everything downstream depends on auth dependency pattern, SQLite configuration (WAL/busy_timeout), and the `talents`/`User` table schemas being correct from the start — all four are cited as "fix now or pay a painful retrofit later."
**Delivers:** FastAPI app skeleton, JWT login (PyJWT + pwdlib[argon2]), `get_current_user` dependency, SQLAlchemy 2.0 models (`Talent`, `User`, `SyncLog` stubs), Alembic migrations, WAL mode + busy_timeout configured, `/health` endpoint, `pydantic-settings` config with all env vars from `.env.example` defined upfront.
**Addresses:** Authentication (table stakes), Talent catalog (data-driven, foundational dependency for all features)
**Avoids:** Pitfall 1 (bcrypt/passlib breakage), Pitfall 2 (JWT secret/expiry strategy), Pitfall 3 (SQLite locking), Pitfall 12 (hardcoded talent catalog)

### Phase 2: Pipedrive Integration + Core Dashboard (M2)
**Rationale:** Pipedrive alone unlocks the majority of P1 table-stakes features (global KPIs, funnel view, per-talent views, lost-opportunity tracking) — this is the "Pipedrive-only dashboard" MVP that validates the consolidation thesis before adding more sources.
**Delivers:** `integrations/pipedrive.py` (adapter + normalization + field-key resolution + pagination), `sync/` module (scheduler + jobs + SyncLog) established as the reusable pattern, `services/funnel.py` + `services/kpis.py`, `routers/dashboard.py` + `routers/talents.py`, global KPI summary, 6-stage funnel view, per-talent ranking/KPI/mini-funnel, lost-opportunity tracking.
**Uses:** httpx-based Pipedrive wrapper, SQLAlchemy upserts, APScheduler
**Implements:** Adapter+Normalization pattern, Sync Job + Local Cache pattern, Talent external-mapping pattern (pipedrive_product_id)
**Avoids:** Pitfall 5 (custom field hash keys), Pitfall 6 (pagination/2000-cap), Anti-Pattern 1 (live API calls on page load)

### Phase 3: Google Sheets Leads Integration (M3)
**Rationale:** Additive data source using the same sync pattern established in M2; lower complexity than Trello, unblocks the Leads dashboard tab.
**Delivers:** `integrations/sheets.py` (gspread + service account, header-based `get_all_records()`), sync job extension, Leads dashboard (classified by talent/source/status), `sheets_tag` mapping column on `Talent`.
**Addresses:** Gmail leads dashboard, lead source/channel classification (P2 features)
**Avoids:** Pitfall 8 (schema drift — header-based access + startup validation), Pitfall 9 (Sheets quota — sync-to-DB, never call gspread from request handlers)

### Phase 4: Trello Integration + Automation (M4)
**Rationale:** Completes the three-source consolidation; revenue projection and collection calendar require both Pipedrive (M2) and Trello data simultaneously, so this phase is the dependency convergence point for the highest-value P2 feature.
**Delivers:** `integrations/trello.py`, sync job extension, `trello_label_id` mapping column, collection calendar, revenue projection (collected/projected/pending), Pipedrive->Trello "won deal" automation with deal_id->trello_card_id linkage table and reconciliation job, brand category breakdown, top campaigns table.
**Implements:** Automation Flow pattern (won deal -> Trello card) with reconciliation, not fire-and-forget webhook
**Avoids:** Pitfall 7 (missed automation events without reconciliation)

### Phase 5: AI-Generated Reports (M5)
**Rationale:** Depends on stable, trustworthy `services/kpis.py`/`funnel.py` (built M2-M4) — AI narration on top of unstable data would produce a poor first impression of the AI feature and risk credibility.
**Delivers:** `integrations/claude.py`, Jinja2 + WeasyPrint PDF pipeline, `Report` table with downloadable history, AI-generated narrative insights for Resumen Ejecutivo.
**Addresses:** AI-generated monthly PDF reports, AI narrative insights (P3 differentiators)
**Avoids:** Pitfall 10 (hallucinated numbers — strict compute/narrate separation, automated number cross-check before finalizing PDF), Pitfall 11 (cost — establish prompt-caching structure here)

### Phase 6: NL Query Agent (M6)
**Rationale:** Requires the same semantic layer (`services/`) as M5, plus a tool-use pattern; explicitly read-only to avoid the "autonomous CRM-modifying agent" anti-feature.
**Delivers:** `services/agent.py` with tool-calling against `services/kpis.py`/`funnel.py` functions (never raw DB/API access), bounded conversation history, prompt caching reused from M5.
**Addresses:** Embedded NL query agent (P3 differentiator)
**Avoids:** Pitfall 10 (tool-use returns exact numbers), Pitfall 11 (history caps + caching), anti-feature "autonomous write-actions"

### Phase 7: Docker/EasyPanel Deployment (M7)
**Rationale:** Final phase — packages the application; SQLite persistence and WeasyPrint system dependencies are the main Docker-specific risks, both well understood by this point.
**Delivers:** Multi-stage Dockerfile (Pango/Cairo/GDK-Pixbuf for WeasyPrint), docker-compose with persistent volume for `seg.db` at a path decided in M1 (e.g. `/data/seg.db`), `.env` configured via EasyPanel secrets (not baked into image), redeploy-survival test.
**Avoids:** Pitfall 4 (SQLite data loss on redeploy — tested explicitly as acceptance criteria)

### Phase Ordering Rationale

- Strict dependency chain: Talent catalog (P1) -> Pipedrive (M2, unlocks most table-stakes) -> Sheets (M3) and Trello (M4, both additive via the same sync pattern) -> AI features (M5/M6, depend on stable services not raw integrations) -> Deploy (M7).
- Revenue projection (the highest-dependency feature) is correctly deferred to M4 since it needs both Pipedrive and Trello data — attempting it in M2 would produce an incomplete/misleading metric.
- M5/M6 are architecturally decoupled from M2-M4 (they read only from local DB via `services/`), so they could theoretically be developed against fixture data in parallel — but the project mandates strict sequential build, which research supports given the "stable services first" requirement for trustworthy AI output.
- Foundational decisions in M1 (WAL mode, talents table, DATABASE_URL path convention, full env-var schema) are each cited as "cheap now, painful retrofit later" — front-loading them avoids touching every downstream module.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Pipedrive):** Custom field hash-key resolution and pagination/cursor specifics — verify exact v1/v2 endpoint shapes and `dealFields` response format at build time.
- **Phase 4 (Trello automation):** Reconciliation job design and webhook ban/retry semantics — confirm Trello API behavior and rate limits at build time.
- **Phase 5 (AI Reports):** Anthropic SDK structured-output API (`output_format=PydanticModel`) is a beta/version-sensitive feature — re-verify against current docs since the SDK ships frequently.
- **Phase 6 (NL Agent):** Tool-use/function-calling pattern and prompt-caching cache_control syntax — confirm current model alias and SDK version at build time.
- **Phase 7 (Deploy):** EasyPanel-specific volume mount behavior is less documented (MEDIUM confidence) — test redeploy-survival explicitly.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** FastAPI/JWT/SQLAlchemy 2.0 patterns are HIGH confidence, officially documented.
- **Phase 3 (Sheets):** gspread + service account + header-based access is a well-documented, stable pattern.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core framework/auth/DB verified against official docs and live PyPI checks; MEDIUM-LOW only on Anthropic SDK structured-output specifics and Pipedrive/Trello client landscape (resolved by recommending httpx wrappers over unmaintained SDKs) |
| Features | MEDIUM-HIGH | Table stakes verified across multiple CRM-analytics and influencer-CRM sources; AI-agent feature patterns are an emerging 2026 category with less established precedent |
| Architecture | HIGH for FastAPI/JWT/layering patterns (official docs); MEDIUM for Pipedrive/Trello sync strategy (community-verified but Pipedrive itself recommends webhooks over polling at scale — research deliberately deviates for this project's size) |
| Pitfalls | HIGH | Auth, SQLite, Pipedrive, Sheets, Trello, and Claude pricing/hallucination pitfalls all verified against current docs/community sources; MEDIUM only for EasyPanel-specific volume persistence behavior |

**Overall confidence:** HIGH

### Gaps to Address

- **Anthropic SDK version drift:** Pin exact version at M5/M6 build time and re-verify structured-output and tool-use API shapes against current docs — the SDK ships multiple releases per month and beta features evolve.
- **EasyPanel volume persistence:** Less documented than general Docker volume practice — must be explicitly tested (redeploy + confirm data survives) as part of M7 acceptance criteria, not assumed from the Dockerfile alone.
- **Pipedrive webhook vs. polling tradeoff:** Research recommends polling for M2-M4 (no stable URL pre-M7) with webhooks as a post-M7 enhancement — confirm this remains the right call once real usage patterns and deal volume are observed.
- **Conversion-rate/bottleneck detection data requirements:** Needs either Pipedrive deal-history endpoint access or a few weeks of accumulated snapshot data post-M2 — timeline for when this becomes meaningful should be revisited during M2/M3 planning.

## Sources

### Primary (HIGH confidence)
- [FastAPI official docs — SQL Databases, Get Current User, OAuth2/JWT tutorial](https://fastapi.tiangolo.com/)
- [PyPI: anthropic, gspread, google-auth, pyjwt, pwdlib, passlib, weasyprint, py-trello](https://pypi.org) — versions checked live June 2026
- [Pipedrive official docs — Custom Fields, Rate Limiting, Deals API v1, Webhooks v2 guide](https://pipedrive.readme.io/)
- [Trello/Atlassian official docs — REST API Rate Limits, Webhooks](https://developer.atlassian.com/cloud/trello/)
- [Google Sheets API usage limits](https://developers.google.com/workspace/sheets/api/limits)
- [Anthropic Claude docs — Reduce hallucinations, Prompt caching](https://docs.anthropic.com/)
- [pyca/bcrypt issue #684 and #1082](https://github.com/pyca/bcrypt/) — reproducible upstream bcrypt/passlib breakage

### Secondary (MEDIUM confidence)
- [fastapi/fastapi PR #13917, Discussions #11345, #9587, #11773](https://github.com/fastapi/fastapi) — passlib/python-jose deprecation status
- [FastAPI Modular Monolith Starter Kit / Modular Monolith FastAPI with SQLModel (GitHub)](https://github.com/) — community architecture references
- Sales pipeline / influencer-CRM / agentic-BI sources (Coupler.io, CaptivateIQ, monday.com, GoodData, CreatorsJet, Knowi, Matz Analytics) — feature landscape and competitor analysis

### Tertiary (LOW confidence)
- [EasyPanel + SQLite + Litestream example (deadcoder0904/easypanel-nextjs-sqlite)](https://github.com/) — inferred EasyPanel volume behavior, needs validation in M7
- WebSearch on Pipedrive Python SDK landscape — absence-of-evidence claim (no maintained official client found)

---
*Research completed: 2026-06-09*
*Ready for roadmap: yes*
