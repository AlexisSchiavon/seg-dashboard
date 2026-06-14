// Dashboard shell: tab switching, sync controls, KPI/ranking/funnel/activity rendering.
// Reuses apiFetch (401 -> /login.html redirect) from auth.js — do not redefine.

const SYNC_POLL_INTERVAL_MS = 2000;
const SYNC_POLL_TIMEOUT_MS = 5 * 60 * 1000; // give up polling after 5 minutes

// Color palette for funnel fill bars (cycling through semantic colors)
const FUNNEL_COLORS = [
  "var(--accent)",
  "var(--amber)",
  "var(--green)",
  "var(--purple)",
  "var(--blue)",
  "var(--text3)",
];

// Avatar background/text color pairs for ranking rows
const AVATAR_COLORS = [
  { bg: "rgba(232,82,10,0.15)", text: "var(--accent)" },
  { bg: "rgba(107,84,214,0.2)", text: "var(--purpleT)" },
  { bg: "rgba(26,158,110,0.15)", text: "var(--greenT)" },
  { bg: "rgba(201,124,20,0.15)", text: "var(--amberT)" },
  { bg: "rgba(36,114,200,0.15)", text: "var(--blueT)" },
];

// ============================================================
// HTML escape helper — must be applied to ALL API-sourced strings
// interpolated into innerHTML to prevent stored XSS (CR-02).
// ============================================================
function escHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function setPage(name) {
  document.querySelectorAll(".page").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".tab").forEach((el) => el.classList.remove("active"));
  document.getElementById("page-" + name).classList.add("active");
  if (event && event.target) {
    event.target.classList.add("active");
  }

  // Load data for the activated tab
  if (name === "overview") {
    loadSummary();
  } else if (name === "funnel") {
    loadFunnel();
  } else if (name === "talent") {
    loadTalentSelector();
  }
}

function showToast(message) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 4000);
}

function formatMinutesAgo(isoTimestamp) {
  if (!isoTimestamp) return null;
  const then = new Date(isoTimestamp);
  if (Number.isNaN(then.getTime())) return null;
  const diffMs = Date.now() - then.getTime();
  return Math.max(0, Math.round(diffMs / 60000));
}

// ============================================================
// Relative time formatting for activity feed
// ============================================================

function formatRelativeTime(isoTimestamp) {
  if (!isoTimestamp) return "Hace un momento";
  const then = new Date(isoTimestamp);
  if (Number.isNaN(then.getTime())) return "Hace un momento";
  const diffMs = Date.now() - then.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "Hace un momento";
  if (diffMin < 60) return `Hace ${diffMin} min`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `Hace ${diffHrs} hora${diffHrs > 1 ? "s" : ""}`;
  const diffDays = Math.floor(diffHrs / 24);
  return `Hace ${diffDays} día${diffDays > 1 ? "s" : ""}`;
}

// ============================================================
// Currency formatting
// ============================================================

function formatMXN(value) {
  if (typeof value !== "number") return "$0";
  if (value >= 1_000_000) {
    return "$" + (value / 1_000_000).toFixed(1) + "M";
  }
  if (value >= 1_000) {
    return "$" + (value / 1_000).toFixed(0) + "K";
  }
  return "$" + value.toFixed(0);
}

// ============================================================
// Empty state renderer
// ============================================================

function renderEmptyState(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = `
    <div class="card" style="text-align:center;padding:32px 16px;">
      <div style="font-size:28px;margin-bottom:12px;">📊</div>
      <div style="font-size:15px;font-weight:500;margin-bottom:8px;">Aún no hay datos de Pipedrive</div>
      <div style="font-size:13px;color:var(--text2);line-height:1.6;">
        Ejecuta la primera sincronización para ver el funnel, el ranking de talentos y las KPIs. Usa el botón 'Sincronizar ahora' arriba.
      </div>
    </div>
  `;
}

// ============================================================
// Sync status
// ============================================================

function renderSyncBanner(syncStatus) {
  const wrap = document.getElementById("sync-banner-wrap");
  if (!wrap) return;

  if (syncStatus && syncStatus.status === "error") {
    const reference = syncStatus.finished_at || syncStatus.started_at;
    const minutesAgo = formatMinutesAgo(reference);
    const hoursAgo = minutesAgo !== null ? Math.max(0, Math.round(minutesAgo / 60)) : "?";
    wrap.innerHTML = `
      <div class="section">
        <div class="alert warn">
          <div class="alert-icon">⚠️</div>
          <div class="alert-text">No se pudo sincronizar — mostrando datos de hace ${hoursAgo} horas</div>
        </div>
      </div>
    `;
  } else {
    wrap.innerHTML = "";
  }
}

function renderSyncPill(syncStatus) {
  const dot = document.getElementById("sync-dot");
  const text = document.getElementById("sync-text");
  if (!dot || !text) return;

  if (!syncStatus || !syncStatus.status) {
    text.textContent = "Última sync: hace -- min";
    dot.style.background = "var(--amber)";
    return;
  }

  const reference = syncStatus.finished_at || syncStatus.started_at;
  const minutesAgo = formatMinutesAgo(reference);

  if (syncStatus.status === "error") {
    text.textContent = minutesAgo !== null
      ? `Última sync: hace ${minutesAgo} min`
      : "Última sync: hace -- min";
    dot.style.background = "var(--amber)";
  } else if (syncStatus.status === "running") {
    text.textContent = "Sincronizando...";
    dot.style.background = "var(--amber)";
  } else {
    text.textContent = minutesAgo !== null
      ? `Última sync: hace ${minutesAgo} min`
      : "Última sync: hace -- min";
    dot.style.background = "var(--green)";
  }
}

async function loadSyncStatus() {
  const res = await apiFetch("/sync/status");
  if (!res) return null; // 401 already redirected
  if (!res.ok) return null;
  const data = await res.json();
  renderSyncPill(data);
  renderSyncBanner(data);
  return data;
}

async function pollSyncUntilDone() {
  const start = Date.now();
  while (Date.now() - start < SYNC_POLL_TIMEOUT_MS) {
    await new Promise((resolve) => setTimeout(resolve, SYNC_POLL_INTERVAL_MS));
    const data = await loadSyncStatus();
    if (!data) return null;
    if (data.status === "success" || data.status === "error") {
      return data;
    }
  }
  return null;
}

async function triggerSync() {
  const btn = document.getElementById("sync-btn");
  if (!btn) return;

  const originalLabel = btn.textContent;
  btn.textContent = "Sincronizando...";
  btn.disabled = true;

  try {
    const res = await apiFetch("/sync/pipedrive", { method: "POST" });
    if (!res) return; // 401 already redirected

    const data = await res.json();

    if (res.status === 202 && data.status === "already_running") {
      showToast("Ya hay una sincronización en curso");
      return;
    }

    if (res.status === 202) {
      const result = await pollSyncUntilDone();
      if (result && result.status === "success") {
        showToast(`Sync completado — ${result.records_synced} deals actualizados`);
        // Refresh dashboard data after successful sync
        loadSummary();
        loadFunnel();
      }
      // On status=="error", renderSyncBanner (called via loadSyncStatus in the
      // finally block below) shows the D-24 failure banner.
    }
  } finally {
    btn.textContent = originalLabel;
    btn.disabled = false;
    loadSyncStatus();
  }
}

// ============================================================
// KPI rendering
// ============================================================

function renderKpis(kpis) {
  const grid = document.getElementById("kpi-grid");
  if (!grid) return;

  grid.innerHTML = kpis.map((tile) => `
    <div class="kpi ${tile.variant}">
      <div class="kpi-label">${tile.label}</div>
      <div class="kpi-val ${tile.variant}">${formatMXN(tile.value)}</div>
      <div class="kpi-sub">MXN${tile.count !== null && tile.count !== undefined ? ` · ${tile.count} deals` : ""}</div>
    </div>
  `).join("");
}

// ============================================================
// Ranking rendering
// ============================================================

function getInitials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function renderRanking(ranking) {
  const container = document.getElementById("ranking-list");
  if (!container) return;

  if (!ranking || ranking.length === 0) {
    container.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin datos de talentos</div>`;
    return;
  }

  const medalClasses = ["gold", "silver", "bronze"];

  container.innerHTML = ranking.map((row, idx) => {
    const isSinTalento = row.is_sin_talento;
    const numDisplay = isSinTalento ? "—" : String(idx + 1);
    const numClass = !isSinTalento && idx < 3 ? ` class="rank-num ${medalClasses[idx]}"` : ` class="rank-num"`;

    let avatarStyle = "";
    if (isSinTalento) {
      avatarStyle = `style="background:var(--bg5);color:var(--text3);"`;
    } else {
      const colorPair = AVATAR_COLORS[idx % AVATAR_COLORS.length];
      avatarStyle = `style="background:${colorPair.bg};color:${colorPair.text};"`;
    }

    const avatarContent = isSinTalento ? "?" : getInitials(row.name);
    const subcopy = row.category
      ? `${escHtml(row.category)} · ${row.deal_count} deal${row.deal_count !== 1 ? "s" : ""}`
      : `${row.deal_count} deal${row.deal_count !== 1 ? "s" : ""}`;

    return `
      <div class="rank-row">
        <div${numClass}>${numDisplay}</div>
        <div class="rank-avatar" ${avatarStyle}>${escHtml(avatarContent)}</div>
        <div class="rank-info">
          <div class="rank-name">${escHtml(row.name)}</div>
          <div class="rank-nicho">${subcopy}</div>
        </div>
        <div class="rank-right">
          <div class="rank-val">${formatMXN(row.revenue)}</div>
        </div>
      </div>
    `;
  }).join("");
}

// ============================================================
// Activity feed rendering
// ============================================================

function renderActivity(activity) {
  const container = document.getElementById("activity-list");
  if (!container) return;

  if (!activity || activity.length === 0) {
    container.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin actividad reciente</div>`;
    return;
  }

  container.innerHTML = activity.map((item) => {
    const relTime = formatRelativeTime(item.detected_at);
    const title = escHtml(item.title || "Deal");
    return `
      <div class="activity-row">
        <div class="act-icon" style="background:var(--greenD);">📝</div>
        <div class="act-text">
          <div class="act-main"><strong>${title}</strong> — ${escHtml(item.talent_name)} pasó a ${escHtml(item.to_stage)}</div>
          <div class="act-time">${relTime} · Pipedrive</div>
        </div>
      </div>
    `;
  }).join("");
}

// ============================================================
// Funnel rendering
// ============================================================

function renderFunnel(stages) {
  const container = document.getElementById("funnel-rows");
  if (!container) return;

  if (!stages || stages.length === 0) {
    container.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin datos de funnel</div>`;
    return;
  }

  const maxCount = Math.max(...stages.map((s) => s.count), 1);

  container.innerHTML = stages.map((stage, idx) => {
    const pct = Math.max((stage.count / maxCount) * 100, stage.count > 0 ? 4 : 0);
    const color = FUNNEL_COLORS[idx % FUNNEL_COLORS.length];
    const countDisplay = stage.count > 0
      ? `<span style="font-size:11px;font-weight:600;color:rgba(255,255,255,0.9);">${stage.count}</span>`
      : "";
    return `
      <div class="funnel-row">
        <span class="f-label">${escHtml(stage.stage)}</span>
        <div class="f-track">
          <div class="f-fill" style="width:${pct}%;background:${color};">${countDisplay}</div>
        </div>
        <span class="f-n">${stage.count}</span>
      </div>
    `;
  }).join("");
}

function renderBottleneck(bottleneck, insufficientData) {
  const slot = document.getElementById("bottleneck-slot");
  if (!slot) return;

  if (insufficientData) {
    slot.innerHTML = `
      <div class="alert info">
        <div class="alert-icon">💡</div>
        <div class="alert-text">Datos insuficientes para detectar cuellos de botella</div>
      </div>
    `;
  } else if (bottleneck) {
    slot.innerHTML = `
      <div class="alert warn">
        <div class="alert-icon">⚠️</div>
        <div class="alert-text"><strong>Cuello de botella detectado:</strong> solo el ${bottleneck.conversion_pct}% de los deals en ${bottleneck.stage_a} avanzan a ${bottleneck.stage_b}.</div>
      </div>
    `;
  } else {
    slot.innerHTML = "";
  }
}

// ============================================================
// Main load functions
// ============================================================

async function loadSummary() {
  const res = await apiFetch("/dashboard/summary");
  if (!res) return; // 401 already redirected

  const data = await res.json();

  if (!data.has_data) {
    // Show empty state in KPI grid area
    const grid = document.getElementById("kpi-grid");
    const rankingList = document.getElementById("ranking-list");
    const activityList = document.getElementById("activity-list");

    if (grid) {
      grid.innerHTML = `
        <div style="grid-column:1/-1;">
          <div style="text-align:center;padding:32px 16px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--rL);">
            <div style="font-size:28px;margin-bottom:12px;">📊</div>
            <div style="font-size:15px;font-weight:500;margin-bottom:8px;">Aún no hay datos de Pipedrive</div>
            <div style="font-size:13px;color:var(--text2);line-height:1.6;">
              Ejecuta la primera sincronización para ver el funnel, el ranking de talentos y las KPIs. Usa el botón 'Sincronizar ahora' arriba.
            </div>
          </div>
        </div>
      `;
    }
    if (rankingList) rankingList.innerHTML = "";
    if (activityList) activityList.innerHTML = "";
    return;
  }

  renderKpis(data.kpis);
  renderRanking(data.ranking);
  renderActivity(data.activity);
}

async function loadFunnel() {
  const res = await apiFetch("/dashboard/funnel");
  if (!res) return; // 401 already redirected

  const data = await res.json();

  if (!data.has_data) {
    const funnelRows = document.getElementById("funnel-rows");
    const bottleneckSlot = document.getElementById("bottleneck-slot");

    if (funnelRows) {
      funnelRows.innerHTML = `
        <div style="text-align:center;padding:32px 16px;">
          <div style="font-size:28px;margin-bottom:12px;">📊</div>
          <div style="font-size:15px;font-weight:500;margin-bottom:8px;">Aún no hay datos de Pipedrive</div>
          <div style="font-size:13px;color:var(--text2);line-height:1.6;">
            Ejecuta la primera sincronización para ver el funnel, el ranking de talentos y las KPIs. Usa el botón 'Sincronizar ahora' arriba.
          </div>
        </div>
      `;
    }
    if (bottleneckSlot) bottleneckSlot.innerHTML = "";
    return;
  }

  renderFunnel(data.stages);
  renderBottleneck(data.bottleneck, data.insufficient_data);
}

// ============================================================
// Por talento tab rendering (Plan 02-03)
// ============================================================

// Donut color palette (6 brand categories)
const DONUT_COLORS = [
  "var(--accent)",
  "var(--purple)",
  "var(--green)",
  "var(--amber)",
  "var(--blue)",
  "var(--text2)",
];

/**
 * Render KPIs into a specific container id (reuses existing KPI tile markup).
 * Allows loadTalentDetail to render into talent-kpis rather than kpi-grid.
 */
function renderKpisInto(kpis, containerId) {
  const grid = document.getElementById(containerId);
  if (!grid) return;

  if (!kpis || kpis.length === 0) {
    grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin KPIs disponibles</div>`;
    return;
  }

  grid.innerHTML = kpis.map((tile) => `
    <div class="kpi ${tile.variant}">
      <div class="kpi-label">${tile.label}</div>
      <div class="kpi-val ${tile.variant}">${formatMXN(tile.value)}</div>
      <div class="kpi-sub">MXN${tile.count !== null && tile.count !== undefined ? ` · ${tile.count} deals` : ""}</div>
    </div>
  `).join("");
}

/**
 * Render the 6-stage per-talent funnel into talent-funnel container.
 * Reuses same markup as global renderFunnel() but targets a different container.
 */
function renderTalentFunnel(stages) {
  const container = document.getElementById("talent-funnel");
  if (!container) return;

  if (!stages || stages.length === 0) {
    container.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin datos de funnel</div>`;
    return;
  }

  const maxCount = Math.max(...stages.map((s) => s.count), 1);

  container.innerHTML = stages.map((stage, idx) => {
    const pct = Math.max((stage.count / maxCount) * 100, stage.count > 0 ? 4 : 0);
    const color = FUNNEL_COLORS[idx % FUNNEL_COLORS.length];
    const countDisplay = stage.count > 0
      ? `<span style="font-size:11px;font-weight:600;color:rgba(255,255,255,0.9);">${stage.count}</span>`
      : "";
    return `
      <div class="funnel-row">
        <span class="f-label">${escHtml(stage.stage)}</span>
        <div class="f-track">
          <div class="f-fill" style="width:${pct}%;background:${color};">${countDisplay}</div>
        </div>
        <span class="f-n">${stage.count}</span>
      </div>
    `;
  }).join("");
}

/**
 * Render active deals into talent-deals container.
 * Shows open deals only (those already in the funnel).
 */
function renderTalentDeals(deals) {
  const container = document.getElementById("talent-deals");
  if (!container) return;

  if (!deals || deals.length === 0) {
    container.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin deals activos</div>`;
    return;
  }

  container.innerHTML = deals.map((deal, idx) => {
    const dotColor = FUNNEL_COLORS[idx % FUNNEL_COLORS.length];
    const sinCotizar = deal.is_sin_cotizar
      ? `<span class="pill" style="background:var(--bg5);color:var(--text2);">Sin cotizar</span>`
      : "";
    return `
      <div class="deal-row">
        <div class="deal-l">
          <div class="deal-dot" style="background:${dotColor};"></div>
          <div>
            <div class="deal-brand">${escHtml(deal.title || "Sin título")}</div>
            <div class="deal-tipo">${escHtml(deal.stage_name || "")}</div>
          </div>
        </div>
        <div class="deal-r">
          <div class="deal-amt">${formatMXN(deal.value || 0)}</div>
          ${sinCotizar}
        </div>
      </div>
    `;
  }).join("");
}

/**
 * Render brand-category donut (conic-gradient) + legend into brand-donut / brand-legend.
 * D-26/D-27: % by deal COUNT, not revenue.
 * Legend format: "{Categoría} — {pct}% ({count} deals)"
 */
function renderBrandDonut(brandCategories) {
  const donutEl = document.getElementById("brand-donut");
  const legendEl = document.getElementById("brand-legend");
  if (!donutEl || !legendEl) return;

  if (!brandCategories || brandCategories.length === 0) {
    // Clear only the donut/legend elements — never destroy the parent card,
    // which would permanently remove #brand-donut and #brand-legend from the
    // DOM and break rendering for all subsequent talent selections (CR-01).
    donutEl.innerHTML = "";
    legendEl.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin categorías de marca registradas todavía</div>`;
    return;
  }

  // Build conic-gradient stops from percentages
  let conicStops = [];
  let cumPct = 0;
  brandCategories.forEach((slice, idx) => {
    const color = DONUT_COLORS[idx % DONUT_COLORS.length];
    conicStops.push(`${color} ${cumPct}% ${cumPct + slice.pct}%`);
    cumPct += slice.pct;
  });
  // Fill remainder if rounding leaves a gap
  if (cumPct < 100) {
    conicStops.push(`var(--bg5) ${cumPct}% 100%`);
  }

  const conicGradient = `conic-gradient(${conicStops.join(", ")})`;

  // Donut via conic-gradient with a circular cutout using radial-gradient mask
  donutEl.innerHTML = `
    <div style="
      width:80px;
      height:80px;
      border-radius:50%;
      background:${conicGradient};
      -webkit-mask:radial-gradient(circle, transparent 30px, black 30px);
      mask:radial-gradient(circle, transparent 30px, black 30px);
      flex-shrink:0;
    "></div>
  `;

  // Legend rows: "{Categoría} — {pct}% ({count} deals)"
  legendEl.innerHTML = brandCategories.map((slice, idx) => {
    const color = DONUT_COLORS[idx % DONUT_COLORS.length];
    const pctDisplay = Number.isFinite(slice.pct) ? slice.pct.toFixed(1) : "0.0";
    return `
      <div style="display:flex;align-items:center;gap:8px;font-size:12px;">
        <div style="width:8px;height:8px;border-radius:50%;background:${color};flex-shrink:0;"></div>
        <div style="color:var(--text2);">${escHtml(slice.category)} — ${pctDisplay}% (${slice.count} deal${slice.count !== 1 ? "s" : ""})</div>
      </div>
    `;
  }).join("");
}

/**
 * Render lost opportunities: per-reason summary line + itemized deal list.
 * D-25: each deal shows a .pill with the resolved razón de pérdida label (never an integer).
 * Empty state: "Sin oportunidades perdidas este periodo"
 */
function renderLostOpportunities(lostSummary, lostOpportunities) {
  const summaryEl = document.getElementById("lost-summary");
  const listEl = document.getElementById("lost-list");
  if (!summaryEl || !listEl) return;

  if (!lostOpportunities || lostOpportunities.length === 0) {
    summaryEl.innerHTML = "";
    listEl.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin oportunidades perdidas este periodo</div>`;
    return;
  }

  // Per-reason summary line: "{N} por {razón}" joined by ", "
  const summaryParts = (lostSummary || []).map((s) => `${s.count} por ${escHtml(s.reason)}`);
  summaryEl.innerHTML = summaryParts.length > 0
    ? `<div style="font-size:12px;color:var(--text2);margin-bottom:10px;">${summaryParts.join(", ")}</div>`
    : "";

  // Itemized list: each lost deal with a .pill showing the loss_reason label
  listEl.innerHTML = lostOpportunities.map((opp) => {
    const pillHtml = opp.loss_reason
      ? `<span class="pill" style="background:var(--blueD);color:var(--blueT);">${escHtml(opp.loss_reason)}</span>`
      : "";
    return `
      <div class="deal-row">
        <div class="deal-l">
          <div class="deal-dot" style="background:var(--red);"></div>
          <div>
            <div class="deal-brand">${escHtml(opp.title || "Sin título")}</div>
          </div>
        </div>
        <div class="deal-r">
          <div class="deal-amt">${formatMXN(opp.amount || 0)}</div>
          ${pillHtml}
        </div>
      </div>
    `;
  }).join("");
}

/**
 * Populate the talent selector from the /dashboard/summary ranking.
 * Clicking a .talent-card calls loadTalentDetail(talentId).
 * Auto-loads the first talent's detail on activation.
 */
async function loadTalentSelector() {
  const selectorEl = document.getElementById("talent-selector");
  if (!selectorEl) return;

  // Reuse already-loaded summary ranking data; fetch if needed
  const res = await apiFetch("/dashboard/summary");
  if (!res) return; // 401 redirected

  const data = await res.json();
  const ranking = (data.ranking || []).filter((r) => !r.is_sin_talento && r.talent_id !== null);

  if (ranking.length === 0) {
    selectorEl.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin talentos disponibles</div>`;
    return;
  }

  selectorEl.innerHTML = ranking.map((talent, idx) => {
    const colorPair = AVATAR_COLORS[idx % AVATAR_COLORS.length];
    const initials = getInitials(talent.name);
    return `
      <div class="talent-card${idx === 0 ? " active" : ""}"
           onclick="selectTalentCard(this, ${talent.talent_id})"
           data-talent-id="${talent.talent_id}">
        <div class="tc-avatar" style="background:${colorPair.bg};color:${colorPair.text};">${escHtml(initials)}</div>
        <div class="tc-name">${escHtml(talent.name)}</div>
        <div class="tc-deals">${talent.deal_count} deals</div>
      </div>
    `;
  }).join("");

  // Auto-load the first talent's detail
  const firstTalent = ranking[0];
  if (firstTalent && firstTalent.talent_id !== null) {
    loadTalentDetail(firstTalent.talent_id);
  }
}

/**
 * Handle talent card selection: update active state + load detail.
 */
function selectTalentCard(cardEl, talentId) {
  // Update active state on all cards in the selector
  const selectorEl = document.getElementById("talent-selector");
  if (selectorEl) {
    selectorEl.querySelectorAll(".talent-card").forEach((c) => c.classList.remove("active"));
  }
  cardEl.classList.add("active");
  loadTalentDetail(talentId);
}

/**
 * Load and render full per-talent detail from GET /dashboard/talents/{id}.
 * Renders into: talent-kpis, talent-funnel, talent-deals, brand-donut/brand-legend, lost-summary/lost-list.
 */
async function loadTalentDetail(talentId) {
  const res = await apiFetch("/dashboard/talents/" + talentId);
  if (!res) return; // 401 redirected

  if (!res.ok) {
    // 404 or other error — show a brief message
    const lostList = document.getElementById("lost-list");
    if (lostList) lostList.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">No se pudo cargar el detalle del talento</div>`;
    return;
  }

  const data = await res.json();

  // (2) KPIs
  renderKpisInto(data.kpis, "talent-kpis");

  // (3) Funnel
  renderTalentFunnel(data.funnel);

  // (4) Active deals — derive from funnel stages (open deals are tracked in funnel)
  // The endpoint returns funnel stages; for "Deals activos" we show a simplified
  // placeholder based on funnel counts since TalentDetail doesn't include raw deal rows.
  // We render the funnel stage rows as a deal activity summary.
  const activeFunnelStages = (data.funnel || []).filter((s) => s.count > 0);
  const talentDealsEl = document.getElementById("talent-deals");
  if (talentDealsEl) {
    if (activeFunnelStages.length === 0) {
      talentDealsEl.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin deals activos</div>`;
    } else {
      talentDealsEl.innerHTML = activeFunnelStages.map((stage, idx) => {
        const dotColor = FUNNEL_COLORS[idx % FUNNEL_COLORS.length];
        return `
          <div class="deal-row">
            <div class="deal-l">
              <div class="deal-dot" style="background:${dotColor};"></div>
              <div>
                <div class="deal-brand">${escHtml(stage.stage)}</div>
                <div class="deal-tipo">${stage.count} deal${stage.count !== 1 ? "s" : ""} activo${stage.count !== 1 ? "s" : ""}</div>
              </div>
            </div>
            <div class="deal-r">
              <div class="deal-amt">${formatMXN(stage.amount)}</div>
            </div>
          </div>
        `;
      }).join("");
    }
  }

  // (5) Brand donut
  renderBrandDonut(data.brand_categories);

  // (6) Lost opportunities
  renderLostOpportunities(data.lost_summary, data.lost_opportunities);
}

// ============================================================
// Initialization
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  loadSyncStatus();
  loadSummary(); // Load Resumen tab on initial page load
});
