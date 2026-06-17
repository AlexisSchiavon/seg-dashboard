// Agente tab: natural-language queries via POST /agent/chat
//
// IMPORTANT: apiFetch, escHtml, showToast defined in auth.js / dashboard.js
// MUST NOT be redefined here. Loaded after dashboard.js and reports.js.
//
// SECURITY — T-6-02 (XSS):
// User-supplied text (question) MUST pass through escHtml() before innerHTML.
// Claude answer is rendered via marked.parse() — user HTML is not injected here
// since this field comes from the Anthropic API, not user input.
// NEVER assign data.answer or user message directly to innerHTML without escaping.

const AGENT_MAX_HISTORY = 20;  // rolling window — D-73

// Configure marked: GFM tables/fenced code, single-newline line breaks
marked.use({ gfm: true, breaks: true });

// In-memory conversation history (cleared on page refresh — D-73)
let _agentHistory = [];

// ============================================================
// initAgentTab — called by setPage('agent') in dashboard.js
// ============================================================

function initAgentTab() {
  // Focus input when tab opens
  const input = document.getElementById("agent-input");
  if (input) input.focus();
}

// ============================================================
// fillAgentInput — chip click pre-fills input (D-72)
// ============================================================

function fillAgentInput(chipEl) {
  const input = document.getElementById("agent-input");
  if (input) {
    input.value = chipEl.textContent.trim();
    input.focus();
  }
}

// ============================================================
// sendAgentMessage — main action
// ============================================================

async function sendAgentMessage() {
  const input = document.getElementById("agent-input");
  const answersEl = document.getElementById("agent-answers");
  const chipsEl = document.getElementById("agent-chips");
  const btnSend = document.getElementById("btn-agent-send");

  const message = input ? input.value.trim() : "";
  if (!message) return;

  // Clear input immediately
  if (input) input.value = "";

  // Hide chips after first message (D-72)
  if (chipsEl) chipsEl.style.display = "none";

  // Disable send button while waiting (T-6-03: rate limiting via UI)
  if (btnSend) { btnSend.disabled = true; btnSend.textContent = "..."; }

  // Prepend loading card (newest cards appear at top)
  const loadingId = "agent-loading-" + Date.now();
  if (answersEl) {
    const loadingCard = document.createElement("div");
    loadingCard.className = "agent-qa-card";
    loadingCard.id = loadingId;
    loadingCard.innerHTML = `
      <div class="agent-qa-question">${escHtml(message)}</div>
      <div class="agent-loading">Consultando datos...</div>
    `;
    answersEl.insertBefore(loadingCard, answersEl.firstChild);
  }

  try {
    const res = await apiFetch("/agent/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: _agentHistory }),
    });

    const loadingEl = document.getElementById(loadingId);

    if (!res || !res.ok) {
      // Error path — do NOT modify history (Pitfall 7)
      if (loadingEl) loadingEl.innerHTML = `
        <div class="agent-qa-question">${escHtml(message)}</div>
        <div class="agent-qa-answer" style="color:var(--redT);">
          Error al consultar el agente. Intenta de nuevo.
        </div>
      `;
      return;
    }

    const data = await res.json();
    const answer = (data.answer || "").trim();

    // Update card with real answer — question stays escaped (user input),
    // answer rendered as Markdown via marked.parse (Claude API output, T-6-02)
    if (loadingEl) {
      loadingEl.innerHTML = `
        <div class="agent-qa-question">${escHtml(message)}</div>
        <div class="agent-qa-answer">${marked.parse(answer)}</div>
      `;
    }

    // Append to rolling history ONLY on success (D-73 / Pitfall 7)
    _agentHistory.push({ role: "user", content: message });
    _agentHistory.push({ role: "assistant", content: answer });

    // Enforce rolling window — keep last AGENT_MAX_HISTORY messages (D-73)
    if (_agentHistory.length > AGENT_MAX_HISTORY) {
      _agentHistory = _agentHistory.slice(_agentHistory.length - AGENT_MAX_HISTORY);
    }

  } catch (err) {
    // Network/parse error — do NOT modify history (Pitfall 7)
    const loadingEl = document.getElementById(loadingId);
    if (loadingEl) loadingEl.innerHTML = `
      <div class="agent-qa-question">${escHtml(message)}</div>
      <div class="agent-qa-answer" style="color:var(--redT);">
        Error inesperado. Intenta de nuevo.
      </div>
    `;
  } finally {
    // Re-enable button regardless of outcome
    if (btnSend) { btnSend.disabled = false; btnSend.textContent = "Preguntar"; }
  }
}

// ============================================================
// clearAgentHistory — Limpiar button (D-74)
// ============================================================

function clearAgentHistory() {
  _agentHistory = [];
  const answersEl = document.getElementById("agent-answers");
  if (answersEl) answersEl.innerHTML = "";
  const chipsEl = document.getElementById("agent-chips");
  if (chipsEl) chipsEl.style.display = "flex";
}

// ============================================================
// Keyboard shortcut: Enter to send (Shift+Enter = newline)
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("agent-input");
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendAgentMessage();
      }
    });
  }
});
