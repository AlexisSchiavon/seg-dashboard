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

  // Reset to placeholder
  select.innerHTML = `<option value="">Selecciona un talento</option>`;

  (talents || []).forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = t.name;
    select.appendChild(opt);
  });
}

// ============================================================
// loadReportMonths — GET /reports/months?talent_id={id}
// ============================================================

/**
 * Populate #report-month based on the selected talent's deals.
 * Called on change of #report-talent.
 * API: GET /reports/months?talent_id={id} → ["2025-05", "2025-04", ...]
 */
async function loadReportMonths(talentId) {
  const monthSelect = document.getElementById("report-month");
  const noMonthsEl = document.getElementById("report-no-months");
  const btnGenerate = document.getElementById("btn-generate");

  if (!monthSelect) return;

  // Reset month dropdown
  monthSelect.innerHTML = `<option value="">Selecciona un mes</option>`;
  monthSelect.disabled = true;
  if (btnGenerate) btnGenerate.disabled = true;
  if (noMonthsEl) noMonthsEl.style.display = "none";

  if (!talentId) return;

  const res = await apiFetch(`/reports/months?talent_id=${encodeURIComponent(talentId)}`);
  if (!res) return; // 401 redirected
  if (!res.ok) {
    showToast("Error al cargar los meses");
    return;
  }

  const months = await res.json();

  if (!months || months.length === 0) {
    // Estado 2 — sin meses disponibles
    if (noMonthsEl) noMonthsEl.style.display = "";
    monthSelect.disabled = true;
    if (btnGenerate) btnGenerate.disabled = true;
    return;
  }

  // Populate month dropdown with formatted labels
  months.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = formatMonthLabel(m);
    monthSelect.appendChild(opt);
  });

  monthSelect.disabled = false;
  if (btnGenerate) btnGenerate.disabled = false;
  if (noMonthsEl) noMonthsEl.style.display = "none";
}

// ============================================================
// generateReport — POST /reports/generate
// ============================================================

/**
 * Trigger report generation with spinner, skeleton preview, then render narrative.
 * Called by onclick of #btn-generate.
 * API: POST /reports/generate {talent_id, month} → ReportOut
 */
async function generateReport() {
  const talentSelect = document.getElementById("report-talent");
  const monthSelect = document.getElementById("report-month");
  const btnGenerate = document.getElementById("btn-generate");
  const btnDownload = document.getElementById("btn-download");
  const previewCard = document.getElementById("pdf-preview-card");
  const previewTitle = document.getElementById("pdf-preview-title");
  const previewSub = document.getElementById("pdf-preview-sub");
  const pdfBody = document.getElementById("pdf-body");

  const talentId = talentSelect ? parseInt(talentSelect.value, 10) : null;
  const month = monthSelect ? monthSelect.value : "";

  if (!talentId || !month) {
    showToast("Selecciona un talento y un mes antes de generar");
    return;
  }

  // Estado 3 — Generando
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

  // Add spin keyframes if not already present
  if (!document.getElementById("spin-keyframes")) {
    const style = document.createElement("style");
    style.id = "spin-keyframes";
    style.textContent = `@keyframes spin { from { transform:rotate(0deg); } to { transform:rotate(360deg); } }`;
    document.head.appendChild(style);
  }

  // Show skeleton in pdf-body
  if (previewCard) previewCard.style.display = "";
  if (pdfBody) {
    pdfBody.innerHTML = `
      <div style="padding:0;">
        <div class="pdf-skeleton" style="width:60%;margin-bottom:16px;"></div>
        <div class="pdf-skeleton" style="width:100%;margin-bottom:4px;"></div>
        <div class="pdf-skeleton" style="width:90%;margin-bottom:4px;"></div>
        <div class="pdf-skeleton" style="width:80%;margin-bottom:20px;"></div>
        <div class="pdf-skeleton" style="width:55%;margin-bottom:12px;"></div>
        <div class="pdf-skeleton" style="width:100%;margin-bottom:4px;"></div>
        <div class="pdf-skeleton" style="width:85%;margin-bottom:20px;"></div>
        <div class="pdf-skeleton" style="width:60%;margin-bottom:12px;"></div>
        <div class="pdf-skeleton" style="width:100%;margin-bottom:4px;"></div>
        <div class="pdf-skeleton" style="width:70%;"></div>
      </div>
    `;
  }

  try {
    const res = await apiFetch("/reports/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ talent_id: talentId, month }),
    });

    if (!res) return; // 401 redirected

    if (!res.ok) {
      // Estado 6 — Error
      if (pdfBody) pdfBody.innerHTML = "";
      if (previewCard) previewCard.style.display = "none";
      showToast("Error al generar el reporte. Intenta de nuevo.");
      return;
    }

    const data = await res.json();
    _currentReportId = data.id;

    // Estado 4 — Reporte generado
    // Populate preview header
    if (previewTitle) {
      previewTitle.textContent = `Reporte mensual · ${data.talent_name}`;
    }
    if (previewSub) {
      previewSub.textContent = `${formatMonthLabel(data.month)} · Generado con IA`;
    }

    // Render 3 narrative blocks — ALL Claude text escaped via escHtml (T-xss)
    if (pdfBody) {
      const narrative = data.narrative || {};
      pdfBody.innerHTML = `
        <div class="pdf-block">
          <div class="pdf-block-title">Resumen ejecutivo</div>
          <div class="pdf-text">${escHtml(narrative.resumen_ejecutivo || "")}</div>
        </div>
        <div class="pdf-block">
          <div class="pdf-block-title">Deals destacados</div>
          <div class="pdf-text">${escHtml(narrative.deals_destacados || "")}</div>
        </div>
        <div class="pdf-block" style="margin-bottom:0;">
          <div class="pdf-block-title">Recomendación</div>
          <div class="pdf-text">${escHtml(narrative.recomendacion || "")}</div>
        </div>
      `;
    }

    // Enable download button and wire to current report
    if (btnDownload) {
      btnDownload.disabled = false;
      btnDownload.onclick = () => downloadReport(data.id);
    }

    showToast("Reporte generado correctamente");
    loadReportHistory();

  } catch (err) {
    // Estado 6 — Error inesperado
    if (pdfBody) pdfBody.innerHTML = "";
    if (previewCard) previewCard.style.display = "none";
    showToast("Error al generar el reporte. Intenta de nuevo.");
  } finally {
    // Reactivar botón con texto original
    if (btnGenerate) {
      btnGenerate.disabled = false;
      btnGenerate.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/>
          <path d="M2 17l10 5 10-5"/>
          <path d="M2 12l10 5 10-5"/>
        </svg>
        Generar reporte con IA`;
    }
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
    const monthLabel = formatMonthLabel(report.month);
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

// ============================================================
// Initialization: wire onChange listener for talent select
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  const talentSelect = document.getElementById("report-talent");
  if (talentSelect) {
    talentSelect.addEventListener("change", (e) => {
      const talentId = e.target.value;
      loadReportMonths(talentId || null);
    });
  }
});
