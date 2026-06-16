# Phase 6: Embedded Natural-Language Agent - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can open a dedicated "Agente" tab in the dashboard and ask natural-language questions about revenue, funnel, leads, and talent performance. The agent calls real Python service functions as tools and returns grounded prose answers — all numeric figures come from Python services, Claude only narrates. The agent is strictly read-only: no write actions against Pipedrive, Trello, Sheets, or the local database.

</domain>

<decisions>
## Implementation Decisions

### Chat UI Placement (AGENT-01)
- **D-70:** Chat interface lives in a **new 6th tab "Agente"** in the tabbar — mirrors the existing 5-tab pattern exactly. New file `frontend/js/agent.js` follows the same module pattern as `reports.js`, `leads.js`, `dashboard.js`.
- **D-71:** Layout is **prompt + answer card**: single text input field at the top, each Q&A pair renders as a card below it (not chat bubbles). Better for reading long agent responses on mobile.
- **D-72:** The Agente tab shows **3-4 clickable starter question chips** when empty — e.g., "¿Cuál es el talento con más revenue?", "¿Cuántos leads entraron esta semana?", "¿Qué deals están en Negociación?". Chips pre-fill the input. Helps users discover what the agent can answer.

### Conversation Memory
- **D-73:** **Multi-turn conversation** — the frontend accumulates a `[{role: "user" | "assistant", content: string}]` array in JS memory and sends the full history on each `POST /agent/chat` request. The backend passes the history to Claude as the `messages` parameter. Agent can reference earlier context within the session (e.g., "¿y cómo se compara con Karamella?" after asking about Mariana). History is cleared on page refresh — no DB storage needed.
- **D-74:** A **"Limpiar" button** (or trash icon) in the tab header resets the JS history array and removes all Q&A cards from the DOM without requiring a page refresh.

### Tool / Data Scope
- **D-75:** **Full set of existing service functions** become agent tools:
  - `global_kpis(db)` — 4 global KPI tiles
  - `talent_ranking(db)` — talent ranking by revenue
  - `talent_detail(db, talent_id)` — per-talent KPIs
  - `funnel_overview(db)` — 6-stage funnel with counts/amounts
  - `talent_funnel(db, talent_id)` — individual talent funnel
  - `recent_activity(db, limit)` — recent deal activity feed
  - `income_projection(db, talent_id)` — monthly income projection
  - `payment_calendar(db, talent_id)` — upcoming payment dates
  - `deals_for_talent(db, talent_id)` — deal list for a talent
  - `leads_summary(db)` — global leads summary
  - `leads_by_talent(db)` — leads grouped by talent
  All are already implemented and tested — zero new service functions needed.
- **D-76:** **Talent name resolution via system prompt** (not a `list_talents` tool): the 21 talent names + IDs are pre-loaded into the system prompt as a JSON block. Claude reads the list and resolves "Mariana" → `talent_id=X` before calling per-talent tools. Adds ~500 tokens per request but eliminates a round-trip tool call.
- **D-77:** **Max 5 tool calls per turn** — if the agentic loop attempts more than 5 tool calls for a single user message, the service returns the partial answer and logs a warning. Prevents runaway loops and unexpected cost spikes.

### Hard Rules (carried from Phase 5 / STATE.md)
- **D-78:** Claude **never invents numeric figures** — all numbers in agent responses come from tool call results (Python services). System prompt must explicitly prohibit fabricating data.
- **D-79:** Agent is **strictly read-only** — no tool may call any write function (Pipedrive, Trello, Sheets, or SQLite). Tools are wrappers over existing read-only service functions only.

### Claude's Discretion
- **Exact system prompt wording** — prompt must include the hard rules (D-78, D-79) and the talent catalog (D-76), but precise phrasing left to planner.
- **Starter question text** — exact wording of the 3-4 chips left to planner; should cover at least one global, one per-talent, and one funnel/leads question.
- **Response streaming vs synchronous** — not discussed; planner decides. Synchronous (matching Phase 5 pattern) is the safer default for internal tooling.
- **Error UX** — what to show when the agent fails (API timeout, rate limit, tool error); left to planner.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 6 Requirements
- `.planning/REQUIREMENTS.md` — AGENT-01 (Phase 6 scope)
- `.planning/ROADMAP.md` §Phase 6 — success criteria (3 items) and goal statement

### Hard Rules
- `.planning/STATE.md` §Blockers/Concerns — "Phase 5/6: Hard rule — Claude narrates only, all numeric figures computed in Python (services/kpis.py, services/funnel.py)"

### Prior Phase Foundation
- `.planning/phases/05-ai-generated-pdf-reports/05-CONTEXT.md` — D-55/D-56/D-57: Claude narrative structure, hard no-numbers rule, model ID (`claude-sonnet-4-6`). Phase 6's agent service follows the same principle.

### Existing Service Layer (all become agent tools — researcher must read)
- `app/services/kpis.py` — `global_kpis`, `talent_ranking`, `talent_detail`
- `app/services/funnel.py` — `funnel_overview`, `talent_funnel`, `recent_activity`
- `app/services/trello_service.py` — `income_projection`, `payment_calendar`, `deals_for_talent`
- `app/services/leads.py` — `leads_summary`, `leads_by_talent`

### Existing Backend Patterns (researcher must read)
- `app/services/reports.py` — Claude API call pattern: `anthropic.Anthropic()` client, system prompt construction, structured output handling. Agent service mirrors this but uses tool-use loop instead of single call.
- `app/routers/reports.py` — router pattern to mirror for `app/routers/agent.py`: router-level `dependencies=[Depends(get_current_user)]`, `def` (not `async def`) endpoint for blocking calls
- `app/auth/dependencies.py` — `get_current_user` dependency to protect `/agent/*` endpoints

### Existing Frontend Patterns (researcher must read)
- `frontend/js/reports.js` — module pattern (top-level functions, `apiFetch`, `escHtml`, `showToast`) that `frontend/js/agent.js` mirrors
- `frontend/index.html` — current 5-tab structure to extend with 6th "Agente" tab (search `tabbar` and `page-` sections)
- `frontend/css/styles.css` — CSS variables and component classes available; planner adds `.agent-*` classes for the new tab

### Stack Reference
- `.planning/research/STACK.md` — `anthropic` SDK tool-use loop pattern; `messages.create` with `tools=` parameter; agentic loop (tool_use → tool_result → assistant response cycle)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/kpis.py`, `funnel.py`, `trello_service.py`, `leads.py` — all 11 tool-backing functions are already implemented, tested, and take `db: Session` as first parameter. Zero new service logic needed.
- `app/services/reports.py` — `anthropic.Anthropic()` client instantiation and `SYSTEM_PROMPT` pattern; agent service adapts this for tool-use loop
- `apiFetch`, `escHtml`, `showToast` — shared JS utilities defined in `auth.js` / `dashboard.js`; available in `agent.js` without redefinition

### Established Patterns
- **Service layer**: business logic in `services/`, router only wires HTTP. Same pattern: `app/services/agent.py` (new) + `app/routers/agent.py` (new)
- **Router-level auth**: `dependencies=[Depends(get_current_user)]` protects all agent endpoints
- **Sync endpoint for blocking calls**: `def` (not `async def`) endpoint in FastAPI router; runs in threadpool (same as `generate_report` in `reports.py`)
- **XSS guard**: all Claude-generated text must pass through `escHtml()` before `innerHTML` assignment (established in `reports.js`)
- **SQLAlchemy session**: `db: Session = Depends(get_db)` — same DB session pattern as all other routers

### Integration Points
- `app/main.py` — register `app/routers/agent.py` with `app.include_router(agent_router, prefix="/agent")`
- `frontend/index.html` tabbar — add 6th tab button + corresponding `#page-agent` section (after `#page-reportes`)
- `frontend/js/agent.js` — loaded after `dashboard.js` and `reports.js` in script order (same pattern as reports.js)
- No new DB models needed — conversation history lives in frontend JS memory only

</code_context>

<specifics>
## Specific Ideas

- Layout: prompt + answer card (not chat bubbles). Input at the top of the tab, Q&A pairs stack below as cards. Each card shows the user question in a muted header + the agent response in the card body.
- Starter chips appear when the history is empty; they disappear once the first Q&A card is rendered.
- "Limpiar" button (or trash icon) in the tab header — resets JS `history` array to `[]` and clears all answer cards from the DOM.
- Multi-turn history: `history = [{role: "user", content: "..."}, {role: "assistant", content: "..."}]` — sent as-is to `POST /agent/chat` body alongside `message` (the new user message). Backend prepends the new message, sends full array to Claude, returns assistant text.
- Max 5 tool calls enforced in `app/services/agent.py` loop: counter incremented per `tool_use` block; if limit reached, break loop and return current partial answer.

</specifics>

<deferred>
## Deferred Ideas

- **Response streaming (SSE)** — not discussed; planner may choose sync (Phase 5 pattern) or streaming. If streaming is chosen, it requires `StreamingResponse` in FastAPI and `EventSource` in frontend JS — planner documents the choice.
- **Conversation persistence across sessions** — history currently clears on page refresh. Persisting to SQLite (a `Conversation` model) deferred to v2.
- **Agent write actions** — any capability for the agent to create/update records in Pipedrive, Trello, or Sheets is explicitly out of scope (REQUIREMENTS.md Out of Scope).

</deferred>

---

*Phase: 6-Embedded Natural-Language Agent*
*Context gathered: 2026-06-16*
