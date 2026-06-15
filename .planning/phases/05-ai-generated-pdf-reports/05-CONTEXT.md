# Phase 5: AI-Generated PDF Reports - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can generate Claude-narrated monthly PDF reports for individual talents from the Reportes tab. All financial figures are computed in Python; Claude provides only prose narrative in three fixed sections. Generated reports are stored on disk and listed in the Reportes tab for download. "Todos los talentos" is explicitly out of scope for this phase.

</domain>

<decisions>
## Implementation Decisions

### Report Scope (REPORT-01)
- **D-53:** Reports are **individual per talent only**. "Todos los talentos" is excluded from this phase. The talent dropdown lists the 21 active talents from the DB; no "all" option.
- **D-54:** The month selector is **dynamic** — shows only months that have deal data in SQLite (not a fixed 12-month lookback). Python queries distinct months from the `Deal` table and returns them ordered descending. If no data exists, the dropdown is empty and the generate button is disabled.

### Claude's Narrative Structure (REPORT-01)
- **D-55:** Claude generates exactly **3 sections**, matching the mockup (`mockup.html` page-reportes):
  1. **Resumen ejecutivo** — narrative summary of the month's activity (leads, deals, revenue)
  2. **Deals destacados** — commentary on notable deals (top by value, stage, at-risk)
  3. **Recomendación** — actionable recommendation (follow-ups, pipeline observations)
- **D-56:** Python pre-computes **all numeric figures** and passes them to Claude as a structured JSON payload. Claude receives: talent name, month, KPI dict (leads, deals by stage, revenue cobrado/proyección/pendiente, top deals list). Claude's task is to produce readable prose from this data — it must NOT invent numbers. The planner writes the exact prompt; the hard rule from STATE.md ("Claude narrates only") is enforced in `services/reports.py`.
- **D-57:** Claude model: `claude-sonnet-4-6` (current model as of build time). The planner should verify the exact model ID in CLAUDE.md at planning time.

### Generation UX (DASH-05)
- **D-58:** Generation is **synchronous with a loading spinner**. The "Generar reporte con IA" button disables itself and shows a spinner while the backend call runs (Claude API + WeasyPrint PDF render, typically 3–10 seconds). No async job queue needed. This is sufficient for an internal tool used occasionally.
- **D-59:** After generation, the PDF is immediately available for download (the "Descargar PDF" button activates). The new report also appears at the top of the history list below.

### PDF Visual Design (REPORT-01)
- **D-60:** The PDF uses a **light / print-friendly theme**: white background, dark text, SEG branding (accent color `#e8520a` for headers/highlights). The in-page preview in the Reportes tab (matching the mockup's dark `pdf-preview` card) is a separate dark-themed HTML preview widget — not the PDF itself. The actual downloaded `.pdf` file is light-themed for readability in print or email.
- **D-61:** PDF template structure (Jinja2): `reports/template.html` (committed to repo). Sections: cover page (talent name, month, "Generado con Claude AI"), then the 3 narrative sections, then a data appendix (KPI table, funnel table). Exact layout details left to planner.

### Report Storage & History (REPORT-02)
- **D-62:** PDFs are stored on disk at `reports/{talent_slug}/{YYYY-MM}.pdf` (e.g., `reports/mariana/2025-05.pdf`). The `reports/` directory is in `.gitignore` and mapped as a Docker volume in Phase 7.
- **D-63:** A `Report` SQLAlchemy model stores metadata per generated report: `id`, `talent_id` (FK), `month` (YYYY-MM string), `generated_at` (datetime), `file_path` (relative), `file_size_bytes`. This is what the history list queries.
- **D-64:** If a report for the same talent + month already exists, **overwrite** it (both the file and the DB row). No versioned history per talent/month — just the latest generation.

### Frontend — Reportes Tab (DASH-05)
- **D-65:** The Reportes tab **does not exist** in the current `frontend/index.html` (the tab bar has 4 tabs: Resumen, Por talento, Funnel, Leads). Phase 5 adds a 5th tab "Reportes" following the mockup's design exactly.
- **D-66:** Frontend JS goes in a new `frontend/js/reports.js` file (consistent with `dashboard.js`, `leads.js` pattern). It handles: loading the talent dropdown, loading the month dropdown, triggering generation, showing spinner, and loading/rendering report history.
- **D-67:** The UI does **not** include a "Compartir por WhatsApp" button (deferred). Only "Generar reporte con IA" (primary) and "Descargar PDF".

### Claude's Discretion
- **Prompt engineering details**: Exact system prompt wording, temperature, max_tokens — left to planner. The constraint is strict: prompt must instruct Claude to use only the provided data and not invent figures.
- **Data appendix content**: Which tables to include in the PDF appendix (beyond the 3 Claude sections) — planner decides based on what's visually useful.
- **Report filename strategy**: Whether to use `talent_slug` derived from `talent.name` or `talent.id` for the file path — left to planner's judgment.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 5 Requirements
- `.planning/REQUIREMENTS.md` — REPORT-01, REPORT-02, DASH-05 (Phase 5 scope)
- `.planning/ROADMAP.md` §Phase 5 — success criteria (3 items) and goal statement

### Visual Reference
- `.planning/reference/mockup.html` — search for `id="page-reportes"` — the Reportes tab UI design: dropdowns, pdf-preview dark card, button layout, history list. This is the UX contract for the frontend.

### Prior Phase Foundation
- `.planning/phases/04-trello-integration-collection-automation/04-CONTEXT.md` — D-20/D-22/D-23/D-24 (sync schedule pattern, manual button, toast/banner UX — carry forward for any sync-related elements)
- `.planning/phases/02-pipedrive-integration-core-dashboard/02-CONTEXT.md` — D-16/D-17 (name matching, Sin talento asignado fallback)

### Existing Backend (researcher must read)
- `app/services/kpis.py` — KPI computation functions that Phase 5's `reports.py` service will call to gather figures for Claude
- `app/services/funnel.py` — funnel computation; Phase 5 needs stage counts and amounts per talent
- `app/models.py` — existing `Talent`, `Deal`, `Lead`, `TrelloCard` models; Phase 5 adds `Report` model
- `app/routers/dashboard.py` — pattern to mirror for `app/routers/reports.py`
- `app/auth/dependencies.py` — `get_current_user` dependency to protect report endpoints

### Existing Frontend (researcher must read)
- `frontend/index.html` — current 4-tab structure to extend with 5th Reportes tab
- `frontend/js/dashboard.js` — JS module pattern to mirror for `frontend/js/reports.js`
- `frontend/css/styles.css` — CSS variables (colors, spacing, components) available for the Reportes tab; `.pdf-section`, `.pdf-preview`, `.pdf-block` classes visible in mockup must be added

### Stack Reference
- `.planning/research/STACK.md` — WeasyPrint system deps (Pango/Cairo for Docker), Jinja2 template pattern, `anthropic` SDK tool-use loop pattern; PDF approach: Python data → Jinja2 HTML → WeasyPrint PDF

### Hard Rules
- STATE.md blocker: "Claude narrates only, all numeric figures computed in Python (services/kpis.py, services/funnel.py)" — enforced at the service layer

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/kpis.py` — KPI functions return per-talent figures already; Phase 5 calls these to build the JSON payload for Claude
- `app/services/funnel.py` — funnel stage data per talent; same call path
- `app/services/leads.py` — leads count per talent per month; can be included in Claude's data payload
- `app/routers/dashboard.py` — router structure to mirror for `app/routers/reports.py`
- `app/auth/dependencies.py` (`get_current_user`) — protect `/reports/*` endpoints with the same dependency
- `frontend/js/leads.js` — module pattern with `loadLeadsSummary()` / `loadLeads()` functions; `reports.js` follows same structure

### Established Patterns
- SQLAlchemy 2.0 declarative models (`Mapped`/`mapped_column`) + Alembic migration for the new `Report` model
- Sync `httpx.Client` for external calls — but the Anthropic SDK handles its own HTTP; use `anthropic.Anthropic()` client directly (no httpx wrapper needed)
- Service layer does business logic, router calls service and returns Pydantic schema — same layering as kpis/funnel/trello_service
- `app/sync/jobs.py` — NOT needed for Phase 5 (report generation is on-demand, not scheduled)

### Integration Points
- `app/services/reports.py` (new) calls `kpis.py` + `funnel.py` + `leads.py` to gather data, then calls Claude API, then renders Jinja2 → PDF via WeasyPrint
- `app/routers/reports.py` (new) exposes: `GET /reports/months?talent_id={id}` (dynamic month list), `POST /reports/generate` (trigger generation), `GET /reports/` (history list), `GET /reports/{id}/download` (file download)
- `frontend/js/reports.js` (new) hooks into the existing tabbar pattern in `frontend/index.html`
- `reports/` directory (new, gitignored) — PDF storage root

</code_context>

<specifics>
## Specific Ideas

- Mockup's inline dark `pdf-preview` card is a UI preview of the report content **before** downloading — it mirrors the 3 Claude sections. The actual PDF file is light-themed. Both must be built: the dark card for the in-page preview, the light Jinja2 template for the actual PDF.
- Mockup shows "✦ Claude AI" badge in the preview header — include this in both the preview and the PDF cover page.
- The PDF preview in the mockup is populated **after** generation (not a static preview before generation) — the "Generar" button call returns the 3 narrative sections + metadata, and the frontend renders them into the preview card before enabling "Descargar".

</specifics>

<deferred>
## Deferred Ideas

- **"Todos los talentos" batch report** — generate one combined PDF with all 21 talents (or a zip of 21 PDFs). Deferred to a future phase or v2 once individual reports are validated.
- **Compartir por WhatsApp** — mockup shows this button. Deferred: `wa.me` deep link with message + download URL. Not in REPORT-01/02 scope.
- **Report scheduling** — auto-generate reports at month end. Deferred to v2 (FUT roadmap).
- **Report versioning** — keeping multiple generations per talent/month. Currently: overwrite. Could track history in v2.

</deferred>

---

*Phase: 5-AI-Generated PDF Reports*
*Context gathered: 2026-06-15*
