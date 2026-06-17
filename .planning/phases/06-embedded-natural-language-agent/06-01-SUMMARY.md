---
phase: 06-embedded-natural-language-agent
plan: "01"
subsystem: agent-backend
tags: [anthropic, tool-use, fastapi, read-only, natural-language]
dependency_graph:
  requires: [app/services/kpis.py, app/services/funnel.py, app/services/trello_service.py, app/services/leads.py, app/auth/dependencies.py, app/database.py]
  provides: [POST /agent/chat endpoint, tool-use agentic loop, ChatRequest/ChatResponse schemas]
  affects: [app/main.py (router registered)]
tech_stack:
  added: []
  patterns: [Anthropic tool-use while loop, router-level auth dependency, def (not async def) blocking endpoint]
key_files:
  created:
    - app/schemas/agent.py
    - app/services/agent.py
    - app/routers/agent.py
    - tests/test_agent.py
  modified:
    - app/main.py
decisions:
  - "MAX_TOOL_CALLS = 5 hard ceiling per turn (D-77) — enforced per tool_use block, not per loop iteration (a single iteration can have parallel tool calls)"
  - "Talent catalog injected into system prompt at request time via DB query (D-76) — adds ~300 tokens, eliminates a round-trip tool call"
  - "def (not async def) endpoint — mirrors reports.py pattern; Anthropic SDK is synchronous blocking, FastAPI runs it in threadpool"
  - "json.dumps with default=str on all tool results — handles datetime objects from recent_activity without TypeError"
metrics:
  duration_minutes: 12
  completed_date: "2026-06-16"
  tasks_completed: 2
  files_changed: 5
---

# Phase 06 Plan 01: Agent Backend (Tool-Use Loop + POST /agent/chat) Summary

**One-liner:** Stateless Anthropic tool-use loop over 11 read-only service functions exposed as `POST /agent/chat` with JWT auth, 5-call ceiling, and talent catalog in system prompt.

## What Was Built

The complete backend slice for the embedded natural-language agent (AGENT-01):

- **`app/schemas/agent.py`** — `ChatMessage`, `ChatRequest` (message min_length=1/max_length=2000, history max_length=20), `ChatResponse` Pydantic v2 models. Pydantic validation returns 422 on violations (T-6-03 input guard).
- **`app/services/agent.py`** — Core implementation:
  - `TOOL_DEFINITIONS` (11 read-only tools, one per service function, each with Spanish description and JSON Schema `input_schema`)
  - `MAX_TOOL_CALLS = 5` (D-77 hard ceiling)
  - `_build_system_prompt(db)` — Spanish role+rules block (D-78 no-invented-figures, D-79 read-only, D-76 talent catalog as JSON from DB query)
  - `_execute_tool(name, tool_input, db)` — if/elif dispatcher with `int()` coercion on `talent_id` and `min(limit, 50)` cap on `recent_activity`
  - `_run_agent_loop(db, message, history)` — while loop: send to Claude, on `stop_reason=="tool_use"` execute tools (tool_result blocks first per Pitfall 1), enforce ceiling, do final synthesis call, return text; on `stop_reason=="end_turn"` return text immediately
  - `chat(db, message, history)` — public entry point for router
- **`app/routers/agent.py`** — `APIRouter(prefix="/agent", dependencies=[Depends(get_current_user)])`, `def chat(body: ChatRequest, db: Session = Depends(get_db))`, ValueError -> HTTP 502 mapping.
- **`app/main.py`** — `app.include_router(agent.router)` added after reports router and before StaticFiles mount.
- **`tests/test_agent.py`** — 8 tests across 3 classes: `TestChatEndpoint` (200/401/422), `TestToolExecutor` (11-tool dispatch + TOOL_DEFINITIONS structure), `TestAgentLoop` (end_turn shortcut + MAX_TOOL_CALLS ceiling).

## Test Results

- `uv run pytest tests/test_agent.py -x -q`: **8/8 passed** (GREEN)
- `uv run pytest tests/ -q`: **153/153 passed** (no regressions)

## TDD Gate Compliance

- RED commit (`36fa3e0`): `test(06-01): add failing tests + ChatRequest/ChatResponse schemas (RED)` — 8 tests failed with ModuleNotFoundError on `app.services.agent`
- GREEN commit (`950b812`): `feat(06-01): implement agent service + router, register in main.py (GREEN)` — all 8 tests pass

## Deviations from Plan

None — plan executed exactly as written.

The plan's read_first references (reports.py analog, conftest.py mock pattern, RESEARCH.md loop code) were all followed verbatim. The mock fixture in `tests/test_agent.py` mirrors the `mock_anthropic` fixture in conftest.py and patches the correct module path (`app.services.agent.anthropic.Anthropic`).

## Known Stubs

None. All 11 tool calls dispatch to real service functions. The system prompt builds the talent catalog from a live DB query. No hardcoded empty values or placeholder text flows to the API response.

## Threat Flags

No new security surface introduced beyond what is in the plan's threat model. All 5 STRIDE threats (T-6-01 through T-6-06) are mitigated as designed:
- T-6-01 (prompt injection): system prompt hard rules + read-only tools only
- T-6-03 (DoS/cost): MAX_TOOL_CALLS=5, ChatRequest size limits via Pydantic
- T-6-04 (history disclosure): stateless — no server-side history storage
- T-6-05 (unauthenticated access): router-level `Depends(get_current_user)` -> 401
- T-6-06 (LLM -> DB): `int()` coercion on talent_id, read-only ORM queries only

## Self-Check: PASSED

Files created/exist:
- app/schemas/agent.py: FOUND
- app/services/agent.py: FOUND
- app/routers/agent.py: FOUND
- tests/test_agent.py: FOUND

Commits:
- 36fa3e0: test(06-01): add failing tests + ChatRequest/ChatResponse schemas (RED)
- 950b812: feat(06-01): implement agent service + router, register in main.py (GREEN)

Full suite: 153/153 passed.
