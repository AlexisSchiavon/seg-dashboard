// Reports tab: talent selector, month picker, AI report generation, PDF download.
//
// IMPORTANT: apiFetch, escHtml, showToast are defined in auth.js / dashboard.js
// and MUST NOT be redefined here. This file is loaded after dashboard.js and leads.js
// (see index.html script order).
//
// SECURITY — T-xss (Pitfall 6):
// ALL strings sourced from Claude narrative (resumen_ejecutivo, deals_destacados,
// recomendacion) MUST pass through escHtml() before innerHTML interpolation.
// No raw Claude text may ever be assigned directly to innerHTML.

// ============================================================
// Month formatting helper
// ============================================================

/**
 * Format "YYYY-MM" → "Mes YYYY" (e.g. "2025-05" → "Mayo 2025").
 * Returns the original string if format is unrecognized.
 */
const MONTH_NAMES_ES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

function formatMonthLabel(yyyyMM) {
  if (!yyyyMM || !/^\d{4}-\d{2}$/.test(yyyyMM)) return yyyyMM;
  const parts = yyyyMM.split("-");
  const year = parts[0];
  const monthIdx = parseInt(parts[1], 10) - 1;
  if (monthIdx < 0 || monthIdx > 11) return yyyyMM;
  return `${MONTH_NAMES_ES[monthIdx]} ${year}`;
}

/**
 * Format a stored period value ("YYYY-MM" or "YYYY-QN") to a human label.
 * Infers month vs quarter from the presence of "Q" and reuses formatPeriodLabel
 * (global, from dashboard.js).
 */
function formatReportPeriod(value) {
  if (!value) return "";
  const type = value.includes("Q") ? "quarter" : "month";
  return formatPeriodLabel(type, value);
}

/**
 * Format a date string ("YYYY-MM-DDTHH:MM:SSZ") to "D MMM" in Spanish.
 * E.g. "2026-06-15T10:00:00" → "15 jun"
 */
function formatShortDate(isoStr) {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  if (isNaN(d.getTime())) return "";
  const day = d.getDate();
  const month = MONTH_NAMES_ES[d.getMonth()].slice(0, 3).toLowerCase();
  return `${day} ${month}`;
}

// ============================================================
// Module-level state: track current report ID for btn-download
// ============================================================

let _currentReportId = null;

// Period filter state (Fase 7). The #report-month select holds the period value
// (month "YYYY-MM" or quarter "YYYY-QN") depending on the active toggle.
// currentMonthValueJS / currentQuarterValueJS / formatPeriodLabel are global
// helpers defined in dashboard.js (loaded before this file).
let _reportPeriodType = 'month';
let _reportPeriodLists = { months: [], quarters: [] };

// ============================================================
// loadReportTalents — GET /reports/talents
// ============================================================

/**
 * Populate #report-talent with active talents from /reports/talents.
 * Called on setPage('reports').
 * Trigger: setPage('reports', event)
 * API: GET /reports/talents → [{id, name}]
 */
async function loadReportTalents() {
  const select = document.getElementById("report-talent");
  if (!select) return;

  const res = await apiFetch("/reports/talents");
  if (!res) return; // 401 → apiFetch already redirected
  if (!res.ok) {
    showToast("Error al cargar los talentos");
    return;
  }

  const talents = await res.json();

  // Reset to placeholder + "Todos los talentos" (Fase 9.6 — consolidado)
  select.innerHTML = `<option value="">Selecciona un talento</option>`
    + `<option value="all">Todos los talentos</option>`;

  (talents || []).forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = t.name;
    select.appendChild(opt);
  });
}

// ============================================================
// loadReportPeriods — GET /reports/months + /reports/quarters (Fase 7)
// ============================================================

/**
 * Load the won-based, global period lists (months + quarters) and populate the
 * #report-month picker for the active toggle. Called on setPage('reports').
 * Both lists come from Deal.won_time (only periods with signings are offered).
 */
async function loadReportPeriods() {
  const [mRes, qRes] = await Promise.all([
    apiFetch("/reports/months"),
    apiFetch("/reports/quarters"),
  ]);
  if (!mRes || !qRes) return; // 401 redirected
  if (!mRes.ok || !qRes.ok) {
    showToast("Error al cargar los periodos");
    return;
  }
  _reportPeriodLists.months = (await mRes.json()) || [];
  _reportPeriodLists.quarters = (await qRes.json()) || [];
  populateReportPeriodSelect();
}

/** Fill #report-month with options for the active period type. */
function populateReportPeriodSelect() {
  const sel = document.getElementById("report-month");
  const noMonthsEl = document.getElementById("report-no-months");
  const btnGenerate = document.getElementById("btn-generate");
  if (!sel) return;

  const isMonth = _reportPeriodType === "month";
  const list = isMonth ? _reportPeriodLists.months.slice() : _reportPeriodLists.quarters.slice();
  const current = isMonth ? currentMonthValueJS() : currentQuarterValueJS();
  if (!list.includes(current)) list.unshift(current);  // D2: always offer current

  if (list.length === 0) {
    // No won deals at all → no periods to report on.
    sel.innerHTML = `<option value="">Sin periodos</option>`;
    sel.disabled = true;
    if (btnGenerate) btnGenerate.disabled = true;
    if (noMonthsEl) noMonthsEl.style.display = "";
    return;
  }

  sel.innerHTML = list
    .map((v) => `<option value="${escHtml(v)}"${v === current ? " selected" : ""}>${escHtml(formatPeriodLabel(_reportPeriodType, v))}</option>`)
    .join("");
  sel.disabled = false;
  if (btnGenerate) btnGenerate.disabled = false;
  if (noMonthsEl) noMonthsEl.style.display = "none";
}

/** Toggle month/quarter mode for the report period picker. */
function setReportPeriodType(type, e) {
  if (type !== "month" && type !== "quarter") return;
  _reportPeriodType = type;
  const toggle = document.getElementById("report-period-toggle");
  if (toggle) {
    toggle.querySelectorAll(".period-toggle-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.ptype === type);
    });
  }
  populateReportPeriodSelect();
}

// ============================================================
// generateReport — POST /reports/generate
// ============================================================

// Original button markup (icon + label) restored after generation.
const BTN_GENERATE_HTML = `
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
  </svg>
  Generar reporte`;

/**
 * Fase 9.6 — generate the PDF and download it directly (fetch → blob).
 * POST /reports/generate now streams the PDF (no JSON), so we read the blob and
 * trigger a browser download using the server's Content-Disposition filename.
 * Talent value "all" → consolidated report ({talent_ids:"all"}).
 */
async function generateReport() {
  const talentSelect = document.getElementById("report-talent");
  const monthSelect = document.getElementById("report-month");
  const btnGenerate = document.getElementById("btn-generate");
  const hint = document.getElementById("report-hint");

  const talentVal = talentSelect ? talentSelect.value : "";
  const periodValue = monthSelect ? monthSelect.value : "";
  if (!talentVal || !periodValue) {
    showToast("Selecciona un talento y un periodo antes de generar");
    return;
  }

  const target = talentVal === "all" ? "all" : [parseInt(talentVal, 10)];
  const body = { talent_ids: target, period_type: _reportPeriodType, period_value: periodValue };

  // Loader — spinner in the button + a hint line (consolidado puede tardar).
  if (!document.getElementById("spin-keyframes")) {
    const style = document.createElement("style");
    style.id = "spin-keyframes";
    style.textContent = `@keyframes spin { from { transform:rotate(0deg); } to { transform:rotate(360deg); } }`;
    document.head.appendChild(style);
  }
  if (btnGenerate) {
    btnGenerate.disabled = true;
    btnGenerate.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
           style="animation:spin 1s linear infinite;">
        <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
      </svg>
      Generando...`;
  }
  if (hint) {
    hint.style.display = "";
    hint.textContent = talentVal === "all"
      ? "Generando reporte consolidado, esto puede tomar unos segundos…"
      : "Generando reporte…";
  }

  try {
    const res = await apiFetch("/reports/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res) return; // 401 redirected

    if (!res.ok) {
      let detail = "Error al generar el reporte. Intenta de nuevo.";
      try { const j = await res.json(); if (j && j.detail) detail = j.detail; } catch (e) { /* non-JSON */ }
      showToast(detail);
      return;
    }

    // Stream → blob → trigger download with the server-provided filename.
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    const match = cd.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : "reporte.pdf";
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    showToast("Reporte descargado");
    loadReportHistory();
  } catch (err) {
    showToast("Error al generar el reporte. Intenta de nuevo.");
  } finally {
    if (btnGenerate) {
      btnGenerate.disabled = false;
      btnGenerate.innerHTML = BTN_GENERATE_HTML;
    }
    if (hint) hint.style.display = "none";
  }
}

// ============================================================
// loadReportHistory — GET /reports/
// ============================================================

/**
 * Fetch and render the report history list into #report-history.
 * Called on setPage('reports') and after successful generation.
 * API: GET /reports/ → [{id, talent_id, talent_name, month, generated_at, file_size_bytes}]
 */
async function loadReportHistory() {
  const container = document.getElementById("report-history");
  if (!container) return;

  const res = await apiFetch("/reports/");
  if (!res) return; // 401 redirected
  if (!res.ok) {
    showToast("Error al cargar el historial de reportes");
    return;
  }

  const reports = await res.json();

  if (!reports || reports.length === 0) {
    container.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Aún no hay reportes generados.</div>`;
    return;
  }

  container.innerHTML = reports.map((report) => {
    const monthLabel = formatReportPeriod(report.month);
    // Talent name and month label are API-sourced — escape before innerHTML (T-xss)
    const talentName = escHtml(report.talent_name || "Desconocido");
    const shortDate = escHtml(formatShortDate(report.generated_at));

    return `
      <div class="deal-row" style="cursor:pointer;" onclick="downloadReport(${report.id})">
        <div class="deal-l">
          <div class="deal-dot" style="background:var(--purpleT);"></div>
          <div>
            <div class="deal-brand">${talentName} · ${escHtml(monthLabel)}</div>
            <div class="deal-tipo">Generado el ${shortDate}</div>
          </div>
        </div>
        <div class="deal-r">
          <span class="pill" style="background:var(--blueD);color:var(--blueT);">PDF</span>
        </div>
      </div>
    `;
  }).join("");
}

// ============================================================
// downloadReport — GET /reports/{id}/download
// ============================================================

/**
 * Trigger PDF download by navigating to the download endpoint.
 * The JWT is carried in a cookie (httpOnly), so a direct window.location
 * navigation works — the browser sends the cookie automatically.
 * @param {number} reportId
 */
function downloadReport(reportId) {
  if (!reportId) return;
  window.location.href = `/reports/${reportId}/download`;
}

// Fase 7: periods are global (won-based), no longer tied to talent selection —
// they are loaded once per tab activation via loadReportPeriods() in setPage().
// No DOMContentLoaded wiring needed here anymore.
