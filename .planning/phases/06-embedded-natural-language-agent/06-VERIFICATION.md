---
phase: 06-embedded-natural-language-agent
verified: 2026-06-16T19:45:00-06:00
status: passed
score: 12/12 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 6: Embedded Natural-Language Agent — Verification Report

**Phase Goal:** Users can ask natural-language questions about dashboard data (revenue, funnel, leads, talents) and receive accurate, read-only answers via an embedded conversational agent.
**Verified:** 2026-06-16T19:45:00-06:00
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /agent/chat returns a prose answer (200 with {answer}) | VERIFIED | `app/routers/agent.py` line 31: `@router.post("/chat", response_model=ChatResponse)`; returns `ChatResponse(answer=answer)`; test `test_chat_returns_answer` passes (8/8 green) |
| 2 | POST /agent/chat returns 401 without authentication | VERIFIED | `app/routers/agent.py` line 24–28: `APIRouter(dependencies=[Depends(get_current_user)])`; `test_chat_requires_auth` asserts 401 and passes |
| 3 | POST /agent/chat returns 422 for empty message | VERIFIED | `app/schemas/agent.py` line 28: `message: str = Field(..., min_length=1, max_length=2000)`; Pydantic enforces 422; `test_chat_empty_message` passes |
| 4 | Agent can only call 11 read-only service functions — no write path exists | VERIFIED | `app/services/agent.py` lines 316–340: `_execute_tool` if/elif chain covers exactly 11 names, all delegate to `kpi_service`, `funnel_service`, `trello_service`, `leads_service` read-only functions; no write imports present; `test_tool_definitions_complete` asserts `len(TOOL_DEFINITIONS) == 11` |
| 5 | Tool-use loop stops after at most 5 tool calls (D-77) | VERIFIED | `app/services/agent.py` line 36: `MAX_TOOL_CALLS = 5`; enforced at lines 400 and 441; `test_max_tool_calls` asserts `tool_call_count <= 5` and passes |
| 6 | System prompt forbids inventing figures (D-78) and write actions (D-79) | VERIFIED | `app/services/agent.py` lines 271–277: "NUNCA inventes cifras..." (D-78) and "Eres SOLO DE LECTURA. No puedes crear, modificar ni eliminar datos..." (D-79) are explicit text in `_build_system_prompt` |
| 7 | User can open a 6th "Agente" tab in the dashboard | VERIFIED | `frontend/index.html` line 27: `<div class="tab" onclick="setPage('agent', event)">Agente</div>` is the 6th tab in `.tabbar` |
| 8 | User can type a question and receive a grounded prose answer as a Q&A card | VERIFIED | `frontend/js/agent.js` lines 46–131: `sendAgentMessage()` reads input, calls `apiFetch("/agent/chat", ...)`, renders answer into `.agent-qa-card` in `#agent-answers`; `frontend/index.html` lines 311–358 provide `#agent-input`, `#btn-agent-send`, `#agent-answers` |
| 9 | Starter question chips appear when conversation is empty and pre-fill input | VERIFIED | `frontend/index.html` lines 340–353: `#agent-chips` with 4 `.agent-chip` buttons; `frontend/js/agent.js` line 34–39: `fillAgentInput(chipEl)` sets `#agent-input` value to chip text |
| 10 | "Limpiar" button clears history and cards without page refresh (D-74) | VERIFIED | `frontend/index.html` line 316: `onclick="clearAgentHistory()"`; `frontend/js/agent.js` lines 137–143: `clearAgentHistory()` resets `_agentHistory = []`, clears `#agent-answers` innerHTML, re-shows `#agent-chips` |
| 11 | Multi-turn history accumulates in JS memory and is sent on each request (D-73) | VERIFIED | `frontend/js/agent.js` line 12: `let _agentHistory = []`; lines 110–116: `_agentHistory.push(user+assistant)` on success only; line 81: `body: JSON.stringify({ message, history: _agentHistory })`; `AGENT_MAX_HISTORY = 20` rolling window enforced |
| 12 | Agent answer text rendered via escHtml/DOMPurify — no raw innerHTML of Claude output (XSS guard) | VERIFIED | `frontend/js/agent.js` line 105: answer rendered as `DOMPurify.sanitize(marked.parse(answer))` — stronger than plan's `escHtml(answer)` (adds Markdown rendering with sanitization); user question rendered via `escHtml(message)` at lines 71, 89, 104; `innerHTML = data.answer` raw pattern is absent |

**Score:** 12/12 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/schemas/agent.py` | ChatMessage, ChatRequest, ChatResponse Pydantic models | VERIFIED | 36 lines; exports all 3 models; `ChatRequest.message` has `min_length=1, max_length=2000`; `history` has `max_length=20` |
| `app/services/agent.py` | Tool definitions, system prompt builder, tool executor, agentic loop | VERIFIED | 465 lines (well above `min_lines: 120`); defines `TOOL_DEFINITIONS` (11 entries), `MAX_TOOL_CALLS`, `_build_system_prompt`, `_execute_tool`, `_run_agent_loop`, `chat` |
| `app/routers/agent.py` | POST /agent/chat endpoint, router-level auth | VERIFIED | 57 lines; `APIRouter(prefix="/agent", dependencies=[Depends(get_current_user)])`; `def chat` (sync, not async); returns `ChatResponse` |
| `tests/test_agent.py` | Tool executor, loop, and endpoint tests | VERIFIED | 8 tests in 3 classes; all 8 pass: `8 passed, 1 warning in 0.20s` |
| `frontend/js/agent.js` | sendAgentMessage, clearAgentHistory, fillAgentInput, initAgentTab | VERIFIED | 159 lines (above `min_lines: 60`); all 4 functions defined; `_agentHistory`, `AGENT_MAX_HISTORY` declared |
| `frontend/index.html` | 6th tab button + #page-agent section | VERIFIED | Line 27: 6th tab; lines 311–358: `#page-agent` with `#agent-input`, `#btn-agent-send`, `#btn-agent-clear`, `#agent-chips` (4 chips), `#agent-answers` |
| `frontend/css/styles.css` | .agent-* dark-mode component classes | VERIFIED | Lines 1851+: `.agent-chip`, `.agent-chip:hover`, `.agent-qa-card`, `.agent-qa-question`, `.agent-qa-answer`, `.agent-loading` all present |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/main.py` | `app.routers.agent.router` | `include_router` | WIRED | Line 27: `app.include_router(agent.router)` — placed before `StaticFiles` mount at line 31 |
| `app/services/agent.py` | kpis/funnel/trello_service/leads service functions | `_execute_tool` dispatch | WIRED | Lines 316–340: complete if/elif chain; all 11 service calls verified |
| `app/routers/agent.py` | `get_current_user` | router-level dependencies | WIRED | Line 27: `dependencies=[Depends(get_current_user)]` |
| `frontend/js/agent.js` | `/agent/chat` | `apiFetch` POST | WIRED | Line 78: `apiFetch("/agent/chat", {method:"POST", ...body: JSON.stringify({message, history: _agentHistory})})` |
| `frontend/js/dashboard.js` | `initAgentTab` | `setPage` agent branch | WIRED | Line 89: `else if (name === "agent") { initAgentTab(); }` |
| `frontend/index.html` | `frontend/js/agent.js` | script tag | WIRED | Line 366: `<script src="/js/agent.js"></script>` — after DOMPurify and marked CDN scripts |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `app/services/agent.py` `_run_agent_loop` | `response.content` | `anthropic.Anthropic().messages.create(...)` with `tools=TOOL_DEFINITIONS` and real service results from `_execute_tool` | Yes — tools delegate to live DB-backed service functions | FLOWING |
| `app/services/agent.py` `_build_system_prompt` | `catalog` | `db.query(Talent.id, Talent.name).filter(Talent.active.is_(True))` | Yes — live DB query | FLOWING |
| `frontend/js/agent.js` `sendAgentMessage` | `data.answer` | `apiFetch("/agent/chat", ...)` → backend tool-use loop | Yes — answer from real Claude call over real service data | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 8 agent tests pass | `uv run pytest tests/test_agent.py -q` | `8 passed, 1 warning in 0.20s` | PASS |
| TOOL_DEFINITIONS has exactly 11 entries | `grep -c '"name":' app/services/agent.py` | 11 `"name":` entries in TOOL_DEFINITIONS block | PASS |
| MAX_TOOL_CALLS = 5 defined | grep check | Line 36: `MAX_TOOL_CALLS = 5` | PASS |
| No debt markers (TBD/FIXME/XXX) in phase files | grep check | "no debt markers" across all 5 modified files | PASS |
| include_router before StaticFiles | position check in main.py | `agent.router` at line 27, `StaticFiles` at line 31 | PASS |
| D-78 rule in system prompt | grep check | Line 271: "NUNCA inventes cifras, montos, porcentajes ni fechas" | PASS |
| D-79 rule in system prompt | grep check | Line 274: "Eres SOLO DE LECTURA. No puedes crear, modificar ni eliminar datos" | PASS |
| Answer XSS-guarded in agent.js | grep check | Line 105: `DOMPurify.sanitize(marked.parse(answer))` — no raw assignment | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| AGENT-01 | 06-01, 06-02 | User can query dashboard data via an embedded NL agent (read-only, no write actions) | SATISFIED | Backend: stateless tool-use loop over 11 read-only service functions, JWT-protected, 5-call ceiling, D-78/D-79 system prompt rules. Frontend: 6th "Agente" tab, Q&A card rendering, multi-turn history, Limpiar, XSS guard. All 8 backend tests pass. |

---

### Anti-Patterns Found

None. No TBD/FIXME/XXX markers, no stub return values, no empty handlers, no raw `innerHTML = data.answer` pattern. The `#agent-answers` container starts empty intentionally — it is populated by real API calls, not hardcoded data.

**Deviation from plan (non-blocking):** Plan 06-02 specified `escHtml(answer)` for answer rendering. The implementation uses `DOMPurify.sanitize(marked.parse(answer))` — this is strictly stronger (sanitized Markdown rendering vs. plain-text HTML escaping). The plan's XSS intent is fully satisfied and exceeded. User question header still uses `escHtml(message)` as specified.

---

### Human Verification Required

The plan included a `checkpoint:human-verify` task (Task 3 of 06-02) requiring browser testing. Per the verification request, human verification was already approved by the user and is treated as passed. The items below are recorded for completeness.

Items that require (or required) browser confirmation:

1. **Grounded answers with real figures**
   - Test: Click a chip, send question, verify the answer number matches the Resumen/Funnel tab
   - Expected: Answer cites actual pipeline/revenue figures from the DB, not invented values
   - Why human: LLM output content cannot be validated by grep

2. **Multi-turn context (D-73)**
   - Test: Ask a follow-up referencing the prior answer
   - Expected: Agent uses conversation context to answer coherently
   - Why human: Requires live Claude API call with real history

3. **Write-action refusal (D-79)**
   - Test: Ask "borra todos los deals" or similar write action
   - Expected: Agent declines, explains it is read-only
   - Why human: Requires live Claude API call to observe system-prompt enforcement

4. **Limpiar UX (D-74)**
   - Test: Send a message, then click Limpiar
   - Expected: Cards clear, chips re-appear, no page refresh
   - Why human: DOM state transition requires browser observation

**Status: approved by user — treated as PASSED**

---

### Gaps Summary

No gaps. All 12 must-haves verified against actual codebase. All artifacts exist, are substantive, and are wired. Data flows from live DB-backed services through the tool-use loop to the frontend Q&A cards. The test suite passes 8/8.

---

_Verified: 2026-06-16T19:45:00-06:00_
_Verifier: Claude (gsd-verifier)_
