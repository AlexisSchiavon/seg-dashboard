---
phase: 6
slug: embedded-natural-language-agent
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-16
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `tests/` directory (existing) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 6-agent-svc | TBD | 1 | AGENT-01 | T-6-01 | Tool calls never write to DB/Pipedrive/Trello/Sheets | unit | `pytest tests/test_agent.py -x -q` | ❌ W0 | ⬜ pending |
| 6-agent-endpoint | TBD | 1 | AGENT-01 | T-6-02 | POST /api/agent/chat returns 200 with text response for valid message | integration | `pytest tests/test_agent.py::test_chat_endpoint -x -q` | ❌ W0 | ⬜ pending |
| 6-tool-schemas | TBD | 1 | AGENT-01 | — | All 11 tool definitions have valid JSON schema (required + type fields) | unit | `pytest tests/test_agent.py::test_tool_definitions -x -q` | ❌ W0 | ⬜ pending |
| 6-rolling-window | TBD | 1 | AGENT-01 | — | History truncated to 20 messages before API call | unit | `pytest tests/test_agent.py::test_rolling_window -x -q` | ❌ W0 | ⬜ pending |
| 6-chat-ui | TBD | 2 | AGENT-01 | T-6-03 | XSS: agent response rendered with escHtml() not innerHTML | manual | See Manual-Only Verifications | N/A | ⬜ pending |
| 6-read-only | TBD | 1 | AGENT-01 | T-6-01 | Agent tools list contains zero write/mutate operations | unit | `pytest tests/test_agent.py::test_tools_are_read_only -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_agent.py` — stubs for AGENT-01 (tool definitions, chat endpoint, rolling window, read-only guard)
- [ ] `tests/conftest.py` — shared DB fixture (already exists from prior phases; extend if needed)

*Existing `pytest` infrastructure covers the framework requirement. Only `tests/test_agent.py` is new.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Chat panel opens/closes via floating button | AGENT-01 | DOM/JS interaction | Click floating chat button → panel appears; click X → panel closes |
| Agent response rendered as HTML-safe text (XSS) | AGENT-01 | Cannot automate XSS escaping verification without a browser | Send message containing `<script>alert(1)</script>`; confirm response shows escaped text, no alert fires |
| Loading spinner shows during agent response | AGENT-01 | Visual UI state | Send any message; confirm spinner appears during 5-15s wait |
| Chat history preserved when switching dashboard tabs | AGENT-01 | Session-scoped memory | Open chat, send message, click to Overview tab, return to chat → history still visible |
| Starter suggestion chips trigger correct queries | AGENT-01 | Interaction state | Click a starter chip; confirm it populates the input and auto-sends |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
