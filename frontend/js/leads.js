// Leads tab: per-talent bars, filterable leads list, D-36 score pills.
//
// IMPORTANT: apiFetch, escHtml, showToast, formatRelativeTime are defined in
// auth.js / dashboard.js and MUST NOT be redefined here. This file is loaded
// after dashboard.js (see index.html script order).
//
// T-03B-01 (Stored XSS mitigation CR-02): every Sheet-sourced string
// (remitente_nombre, remitente_email, asunto, talent_name, status_display)
// MUST pass through escHtml() before innerHTML interpolation.

// ============================================================
// Score pill color helper (D-36)
// ============================================================

/**
 * Return {bg, text} CSS variable pair for a score pill.
 * 0-40  → red   (--redD / --redT)
 * 41-70 → amber (--amberD / --amberT)
 * 71-100 → green (--greenD / --greenT)
 * null/undefined → neutral grey
 */
function scorePillColor(score) {
  if (score == null || score === undefined) {
    return { bg: "var(--bg4)", text: "var(--text2)" };
  }
  if (score <= 40) {
    return { bg: "var(--redD)", text: "var(--redT)" };
  }
  if (score <= 70) {
    return { bg: "var(--amberD)", text: "var(--amberT)" };
  }
  return { bg: "var(--greenD)", text: "var(--greenT)" };
}

// ============================================================
// Status pill color helper
// ============================================================

/**
 * Return inline style string for a status display pill.
 * Aprobado → green, Bloqueado → red, En revisión → amber, unknown → blue
 */
function statusPillStyle(statusDisplay) {
  if (statusDisplay === "Aprobado") {
    return "background:var(--greenD);color:var(--greenT);";
  }
  if (statusDisplay === "Bloqueado") {
    return "background:var(--redD);color:var(--redT);";
  }
  if (statusDisplay === "En revisión") {
    return "background:var(--amberD);color:var(--amberT);";
  }
  return "background:var(--blueD);color:var(--blueT);";
}

// ============================================================
// Per-talent bar rendering (Leads por talento section)
// ============================================================

/**
 * Render KPI tiles and per-talent bars from /leads/summary response.
 * Populates #leads-kpi-grid and #leads-by-talent.
 * Talent names escaped via escHtml (T-03B-01).
 */
function renderLeadsSummary(data) {
  // --- KPI tiles ---
  const kpiGrid = document.getElementById("leads-kpi-grid");
  if (kpiGrid) {
    const totales = data.leads_totales || 0;
    const calificados = data.calificados || 0;
    const pct = totales > 0 ? Math.round((calificados / totales) * 100) : 0;
    kpiGrid.innerHTML = `
      <div class="kpi">
        <div class="kpi-label">Leads totales</div>
        <div class="kpi-val">${totales}</div>
        <div class="kpi-sub">Sincronizados</div>
      </div>
      <div class="kpi green">
        <div class="kpi-label">Calificados</div>
        <div class="kpi-val green">${calificados}</div>
        <div class="kpi-sub">${pct}% del total</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Tasa de calidad</div>
        <div class="kpi-val ${pct >= 50 ? "green" : pct >= 25 ? "amber" : "red"}">${pct}%</div>
        <div class="kpi-sub">Aprobados / Total</div>
      </div>
    `;
  }

  // --- Per-talent bars ---
  const talentContainer = document.getElementById("leads-by-talent");
  if (!talentContainer) return;

  const bars = data.por_talento || [];
  if (bars.length === 0) {
    talentContainer.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin datos de talentos</div>`;
    return;
  }

  // Max total for bar width calculation (exclude zero to avoid division issues)
  const maxTotal = Math.max(...bars.map((b) => b.total), 1);

  // Separate "Sin talento asignado" bucket to render last
  const regularBars = bars.filter((b) => !b.is_sin_talento);
  const sinTalentoBucket = bars.find((b) => b.is_sin_talento);
  const orderedBars = sinTalentoBucket ? [...regularBars, sinTalentoBucket] : regularBars;

  talentContainer.innerHTML = orderedBars.map((bar) => {
    const initials = bar.is_sin_talento
      ? "?"
      : bar.name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
    const pct = maxTotal > 0 ? Math.round((bar.total / maxTotal) * 100) : 0;
    const iconStyle = bar.is_sin_talento
      ? "background:var(--bg5);color:var(--text3);"
      : "background:var(--accent);color:#fff;opacity:0.85;";
    return `
      <div class="source-row">
        <div class="source-icon" style="${iconStyle}">${escHtml(initials)}</div>
        <div class="source-info">
          <div class="source-name">${escHtml(bar.name)}</div>
          <div class="source-count">${bar.total} leads · ${bar.calificados} calificados</div>
        </div>
        <div class="source-bar-wrap">
          <div class="source-bar-track">
            <div class="source-bar-fill" style="width:${pct}%;"></div>
          </div>
          <div class="source-pct">${bar.total}</div>
        </div>
      </div>
    `;
  }).join("");
}

// ============================================================
// Leads list rendering
// ============================================================

/**
 * Render each lead as a .deal-row with score pill and status pill.
 * ALL Sheet-sourced strings escaped via escHtml (T-03B-01 CR-02 mitigation).
 */
function renderLeadsList(leads) {
  const container = document.getElementById("leads-list");
  if (!container) return;

  if (!leads || leads.length === 0) {
    container.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin leads</div>`;
    return;
  }

  container.innerHTML = leads.map((lead) => {
    const scoreColors = scorePillColor(lead.score_calidad);
    const scorePill = `<span class="pill" style="background:${scoreColors.bg};color:${scoreColors.text};">${lead.score_calidad != null ? lead.score_calidad : "—"}</span>`;

    const statusDisplay = escHtml(lead.status_display || lead.status_filtrado);
    const statusPill = `<span class="pill" style="${statusPillStyle(lead.status_display)}">${statusDisplay}</span>`;

    // Fase 8.4: talent name is clickable to filter the list — but only when the
    // lead actually has a talent (filtering by "Sin talento asignado"/null is
    // meaningless). event.stopPropagation keeps the row's openLeadModal from firing.
    const talentLabel = (lead.talent_id != null && lead.talent_name)
      ? `<span class="lead-talent-link" onclick="event.stopPropagation(); filterByTalent(${lead.talent_id})">${escHtml(lead.talent_name)}</span>`
      : `<span class="lead-talent-muted">Sin talento asignado</span>`;
    const dotColor = lead.bloqueado
      ? "var(--red)"
      : lead.status_display === "Aprobado"
      ? "var(--green)"
      : "var(--amber)";

    return `
      <div class="deal-row lead-row-clickable" onclick="openLeadModal(${lead.id})">
        <div class="deal-l">
          <div class="deal-dot" style="background:${dotColor};"></div>
          <div>
            <div class="deal-brand">${escHtml(lead.remitente_nombre)} · ${escHtml(lead.remitente_email)}</div>
            <div class="deal-tipo">${talentLabel} · ${escHtml(lead.asunto)}</div>
          </div>
        </div>
        <div class="deal-r">
          ${statusPill}
          ${scorePill}
        </div>
      </div>
    `;
  }).join("");
}

// ============================================================
// Populate filter dropdowns from summary data
// ============================================================

/**
 * Populate #filter-talent <select> from the por_talento list.
 * Called once after loadLeadsSummary resolves.
 */
function populateTalentFilter(bars) {
  const select = document.getElementById("filter-talent");
  if (!select) return;

  // Keep the "Todos" option, rebuild the rest
  select.innerHTML = `<option value="">Todos los talentos</option>`;
  const regularBars = (bars || []).filter((b) => !b.is_sin_talento);
  regularBars.forEach((bar) => {
    const opt = document.createElement("option");
    opt.value = bar.talent_id;
    opt.textContent = bar.name;
    select.appendChild(opt);
  });
}

// ============================================================
// Data loaders
// ============================================================

/**
 * Fetch /leads/summary, render KPI tiles + per-talent bars,
 * and populate the talent filter dropdown.
 */
async function loadLeadsSummary() {
  const res = await apiFetch("/leads/summary");
  if (!res) return; // 401 → apiFetch already redirected to /login.html
  if (!res.ok) {
    showToast("Error cargando resumen de leads");
    return;
  }
  const data = await res.json();
  renderLeadsSummary(data);
  populateTalentFilter(data.por_talento || []);
}

/**
 * Fetch /leads with optional filters from the dropdown selects,
 * then render the leads list.
 */
async function loadLeads() {
  const talentId = (document.getElementById("filter-talent") || {}).value || "";
  const status = (document.getElementById("filter-status") || {}).value || "";
  const fuente = (document.getElementById("filter-fuente") || {}).value || "";

  const params = new URLSearchParams();
  if (talentId) params.append("talent_id", talentId);
  if (status) params.append("status", status);
  if (fuente) params.append("fuente", fuente);

  const qs = params.toString() ? "?" + params.toString() : "";
  const res = await apiFetch(`/leads${qs}`);
  if (!res) return; // 401 redirect
  if (!res.ok) {
    // 404 = talent_id not in DB (Fase 8.4) — friendly message, not a raw error.
    if (res.status === 404) {
      showToast("Talento no encontrado");
      renderLeadsList([]);
    } else {
      showToast("Error cargando leads");
    }
    updateTalentChip();
    return;
  }
  const leads = await res.json();
  renderLeadsList(leads);
  updateTalentChip(); // keep the chip in sync regardless of how the filter was set (D6)
}

// ============================================================
// Talent filter chip (Fase 8.4)
// ============================================================

/** Click a talent in a lead row → select it in the dropdown and refilter. */
function filterByTalent(talentId) {
  const sel = document.getElementById("filter-talent");
  if (sel) sel.value = String(talentId);
  loadLeads(); // loadLeads() refreshes the chip via updateTalentChip()
}

/** The chip's × clears the talent filter back to "Todos los talentos". */
function clearTalentFilter() {
  const sel = document.getElementById("filter-talent");
  if (sel) sel.value = "";
  loadLeads();
}

/**
 * Render (or hide) the "Talento: <nombre> [×]" chip from the CURRENT dropdown
 * state, so it reflects the filter whether it was set via the dropdown or a
 * row click. The label is read from the selected <option> text.
 */
function updateTalentChip() {
  const chip = document.getElementById("leads-filter-chip");
  const sel = document.getElementById("filter-talent");
  if (!chip) return;

  const value = sel ? sel.value : "";
  if (!value) {
    chip.style.display = "none";
    chip.innerHTML = "";
    return;
  }

  const opt = sel.options[sel.selectedIndex];
  const label = opt ? opt.text : value;
  chip.style.display = "";
  chip.innerHTML =
    `<span class="leads-chip">Talento: ${escHtml(label)}` +
    `<button class="leads-chip-x" onclick="clearTalentFilter()" aria-label="Quitar filtro">&times;</button>` +
    `</span>`;
}

// ============================================================
// Lead detail modal (Fase 8.3)
// ============================================================

/**
 * Reformat a plain-text email body into safe display HTML (D11, revised per H-08-03).
 *
 * Security ordering is critical:
 *   1. HTML-escape the raw input first (so any markup becomes inert text),
 *   2. then apply the readability heuristics on the escaped text,
 *   3. then turn the controlled markers \n -> <br> and *x* -> <strong>x</strong>.
 * A malicious "*<script>*" becomes "*&lt;script&gt;*" after escaping and finally
 * "<strong>&lt;script&gt;</strong>" — completely inert.
 *
 * Format detection (H-08-03): real bodies already contain "\n", so we RESPECT the
 * existing line breaks and skip the line-rebuilding rules (1-5). Only the no-newline
 * fallback (old/malformed leads) gets the full split heuristics.
 *
 * Returns null for empty/null input — the caller renders the D7 fallback copy.
 */
function formatLeadEmail(text) {
  if (!text) return null;

  // Step 1: escape HTML.
  let safe = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Step 2: only rebuild line breaks when the source has none.
  const hasNewlines = safe.includes("\n");
  if (!hasNewlines) {
    safe = safe.replace(/\s+/g, " ");
    safe = safe.replace(/,([A-ZÁÉÍÓÚÑ])/g, ",\n\n$1");
    safe = safe.replace(/\.([A-ZÁÉÍÓÚÑ])/g, ".\n\n$1");
    safe = safe.replace(/([a-záéíóúñ])([A-ZÁÉÍÓÚÑ])/g, "$1\n\n$2");
    safe = safe.replace(/^(Abrazo|Saludos|Atentamente|Best),/gm, "\n\n$1,");
  }

  // Step 3 (always): markdown bold + newlines -> <br>.
  safe = safe.replace(/\*(.+?)\*/g, "<strong>$1</strong>");
  safe = safe.replace(/\n/g, "<br>");

  return safe;
}

/**
 * Fetch GET /leads/{id} and render the detail modal.
 * The whole lead row calls this with the lead id.
 */
async function openLeadModal(leadId) {
  const res = await apiFetch(`/leads/${encodeURIComponent(leadId)}`);
  if (!res) return; // 401 redirected
  if (!res.ok) {
    showToast("No se pudo cargar el detalle del lead");
    return;
  }
  const lead = await res.json();
  renderLeadModal(lead);

  const modal = document.getElementById("lead-modal");
  if (modal) modal.classList.add("open");
}

/** Populate the modal DOM from a LeadDetail object (all values escaped/controlled). */
function renderLeadModal(lead) {
  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };

  // Header
  setText("lead-modal-title", lead.remitente_nombre || lead.remitente_email || "Lead");
  const fecha = lead.fecha_recepcion ? formatLeadDate(lead.fecha_recepcion) : "Sin fecha";
  setText("lead-modal-sub", `${lead.remitente_email} · ${fecha}`);

  const statusEl = document.getElementById("lead-modal-status");
  if (statusEl) {
    const display = lead.status_display || lead.status_filtrado;
    statusEl.textContent = display;
    statusEl.setAttribute("style", `${statusPillStyle(display)}`);
  }

  // Truncation banner (D8)
  const banner = document.getElementById("lead-modal-trunc");
  if (banner) banner.style.display = lead.email_truncated ? "" : "none";

  // Email section — asunto + body (D7 fallback when null)
  setText("lead-modal-asunto", lead.asunto || "(Sin asunto)");
  const bodyEl = document.getElementById("lead-modal-body");
  if (bodyEl) {
    const html = formatLeadEmail(lead.email_completo);
    if (html === null) {
      bodyEl.textContent = "Cuerpo del email no disponible para este lead";
      bodyEl.classList.add("lead-email-empty");
    } else {
      bodyEl.innerHTML = html; // safe: formatLeadEmail escaped first, then added controlled tags
      bodyEl.classList.remove("lead-email-empty");
    }
  }

  // Classification section — 5 fields with D7 fallbacks
  const grid = document.getElementById("lead-modal-classification");
  if (grid) {
    const score = lead.score_calidad != null ? String(lead.score_calidad) : "—";
    const rows = [
      ["Status", lead.status_display || lead.status_filtrado],
      ["Score", score],
      ["Razón", lead.razon_validacion || "Sin razón registrada"],
      ["Talento", lead.talent_name || "Sin talento asignado"],
      ["Categoría", lead.categoria_detectada || "Sin categoría"],
    ];
    grid.innerHTML = rows
      .map(
        ([label, value]) =>
          `<div class="lead-class-label">${escHtml(label)}</div>` +
          `<div class="lead-class-value">${escHtml(value)}</div>`,
      )
      .join("");
  }
}

/** Format an ISO date for the modal header, e.g. "30 mar 2026, 17:39". */
function formatLeadDate(isoStr) {
  const d = new Date(isoStr);
  if (isNaN(d.getTime())) return "Sin fecha";
  const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${d.getDate()} ${meses[d.getMonth()]} ${d.getFullYear()}, ${hh}:${mm}`;
}

function closeLeadModal() {
  const modal = document.getElementById("lead-modal");
  if (modal) modal.classList.remove("open");
}

/** Backdrop click closes only when the click is on the overlay itself. */
function handleLeadModalBackdrop(e) {
  if (e.target === document.getElementById("lead-modal")) closeLeadModal();
}

// ============================================================
// DOM wiring — guarded so this file can be require()'d in Node tests
// (formatLeadEmail is a pure function; the rest needs a browser DOM).
// ============================================================

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    ["filter-talent", "filter-status", "filter-fuente"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("change", () => loadLeads());
    });
  });

  // ESC closes the lead modal (the settings modal has no ESC handler; this is new).
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeLeadModal();
  });
}

// Node test hook (no-op in the browser, where `module` is undefined).
if (typeof module !== "undefined" && module.exports) {
  module.exports = { formatLeadEmail };
}
