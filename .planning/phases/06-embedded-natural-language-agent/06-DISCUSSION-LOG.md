# Phase 6: Embedded Natural-Language Agent - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-16
**Phase:** 06-embedded-natural-language-agent
**Areas discussed:** Chat UI placement, Conversation memory, Tool / data scope

---

## Chat UI Placement

### Q1: Where should the chat interface live?

| Option | Description | Selected |
|--------|-------------|----------|
| New 6th tab 'Agente' | Mirrors existing 5-tab pattern; new frontend/js/agent.js | ✓ |
| Floating overlay panel | Sticky FAB opens a chat drawer over any tab | |
| Embedded in Resumen tab | Chat section below KPI tiles, no new tab | |

**User's choice:** New 6th tab 'Agente'
**Notes:** Consistent with existing tabbar pattern; clean separation.

---

### Q2: What should the Agente tab look like?

| Option | Description | Selected |
|--------|-------------|----------|
| Simple chat bubble layout | User right, agent left — WhatsApp/iMessage style | |
| Prompt + answer card | Input at top, Q&A pairs as cards below | ✓ |
| You decide | Leave exact visual layout to planner | |

**User's choice:** Prompt + answer card
**Notes:** Better for reading long agent responses; simpler card-based layout.

---

### Q3: Should the tab include starter question chips?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — 3-4 clickable prompts | Chips pre-fill the input, help users discover capabilities | ✓ |
| No — plain input only | Just a text input and submit button | |

**User's choice:** Yes — 3-4 clickable prompts
**Notes:** Appears when history is empty; disappears after first Q&A.

---

## Conversation Memory

### Q1: Multi-turn or single-turn?

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-turn — history in memory | Frontend accumulates history array, sent on each request; clears on refresh | ✓ |
| Single-turn — each question independent | Fresh call per question, no prior context | |

**User's choice:** Multi-turn — history in memory
**Notes:** No DB storage needed. Enables contextual follow-ups within a session.

---

### Q2: Clear conversation button?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — 'Limpiar' / trash icon | Resets JS history + removes cards from DOM | ✓ |
| No — refresh to clear | Page reload to start fresh | |

**User's choice:** Yes — 'Limpiar' / trash icon button in tab header.

---

## Tool / Data Scope

### Q1: Which service functions become agent tools?

| Option | Description | Selected |
|--------|-------------|----------|
| Full set — all existing services | All 11 service functions exposed as tools | ✓ |
| Curated set — global + per-talent KPIs/funnel | Excludes Trello-specific tools (income_projection, payment_calendar) | |
| Minimal — global queries only | global_kpis, talent_ranking, funnel_overview, leads_summary only | |

**User's choice:** Full set — all existing services
**Notes:** All 11 functions already implemented and tested — zero new service logic.

---

### Q2: How does the agent resolve talent names?

| Option | Description | Selected |
|--------|-------------|----------|
| No — pass talent list in system prompt | 21 names+IDs pre-loaded in system prompt as JSON block | ✓ |
| Yes — include a list_talents tool | Extra tool call to resolve name → ID | |

**User's choice:** Pass talent list in system prompt
**Notes:** Adds ~500 tokens per request; eliminates an extra tool call round-trip.

---

### Q3: Max tool calls per turn?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — cap at 5 tool calls per turn | Break loop and return partial answer if exceeded | ✓ |
| No explicit cap | Let Claude call as many tools as needed | |

**User's choice:** Yes — cap at 5 tool calls per turn
**Notes:** Safety net against runaway loops and unexpected API costs.

---

## Claude's Discretion

- **Exact system prompt wording** — must include hard no-numbers rule and talent catalog JSON, but precise phrasing left to planner
- **Starter question text** — exact wording of 3-4 chips; should cover global, per-talent, and funnel/leads questions
- **Response streaming vs synchronous** — not discussed; planner decides (synchronous = safer default)
- **Error UX** — what to show on API timeout, rate limit, or tool call failure; left to planner

## Deferred Ideas

- **Response streaming (SSE)** — not discussed during this session; deferred to planner's discretion
- **Conversation persistence across sessions** — history clears on page refresh; SQLite-backed persistence deferred to v2
- **Agent write actions** — explicitly out of scope per REQUIREMENTS.md
