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

    const talentLabel = lead.talent_name
      ? escHtml(lead.talent_name)
      : "Sin talento asignado";
    const dotColor = lead.bloqueado
      ? "var(--red)"
      : lead.status_display === "Aprobado"
      ? "var(--green)"
      : "var(--amber)";

    return `
      <div class="deal-row">
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
    showToast("Error cargando leads");
    return;
  }
  const leads = await res.json();
  renderLeadsList(leads);
}

// ============================================================
// Filter change listeners (wired when DOM is ready via index.html onload order)
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  ["filter-talent", "filter-status", "filter-fuente"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", () => loadLeads());
  });
});
