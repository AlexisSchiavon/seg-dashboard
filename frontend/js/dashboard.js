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

// Campaign filter state (module-level so setCampaignFilter can re-render without re-fetching)
let _campaignDeals = null;
let _campaignLostOpps = null;
let _campaignFilter = 'all';

// KPI toggle state (Por Talento view)
let _kpiView = 'flujo';
let _talentDetailData = null;

// Period filter state (Fase 7) — Por Talento. Default = current month (D2).
// Initialized synchronously so the first loadTalentDetail() always has a value,
// even before the period dropdowns finish loading.
let _currentTalentId = null;
let _talentPeriod = { type: 'month', value: null };  // value set below at load
let _talentPeriodLists = { months: [], quarters: [] };

// KPI tiles that are a live state (D4) — NOT scoped by the period filter.
// "Pendiente por cobrar" (Flujo view) and "Pipeline" (Operativa view).
const SNAPSHOT_KPI_LABELS = new Set(['Pendiente por cobrar', 'Pipeline']);

// Spanish month names for period labels (dashboard.js loads before reports.js,
// so it cannot borrow reports.js's MONTH_NAMES_ES — keep a local copy).
const MONTH_NAMES_ES_DASH = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];

/** Current month as "YYYY-MM" (local time). */
function currentMonthValueJS() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

/** Current quarter as "YYYY-QN" (local time). */
function currentQuarterValueJS() {
  const d = new Date();
  return `${d.getFullYear()}-Q${Math.floor(d.getMonth() / 3) + 1}`;
}

/** Human label for a period value, e.g. "Junio 2026" or "Q2 2026". */
function formatPeriodLabel(type, value) {
  if (!value) return '—';
  if (type === 'quarter') {
    const m = /^(\d{4})-Q([1-4])$/.exec(value);
    return m ? `Q${m[2]} ${m[1]}` : value;
  }
  const m = /^(\d{4})-(\d{2})$/.exec(value);
  if (!m) return value;
  const idx = parseInt(m[2], 10) - 1;
  return idx >= 0 && idx < 12 ? `${MONTH_NAMES_ES_DASH[idx]} ${m[1]}` : value;
}

// Resolve the default period value now (D2) so the first detail load is scoped.
_talentPeriod.value = currentMonthValueJS();

const CAMPAIGN_FILTERS = [
  { key: 'all',         label: 'Todos',       cls: '' },
  { key: 'llamada',     label: 'Llamada',      cls: 'llamada' },
  { key: 'cotizacion',  label: 'Cotización',   cls: 'cotizacion' },
  { key: 'negociacion', label: 'Negociación',  cls: 'negociacion' },
  { key: 'contrato',    label: 'Contrato',     cls: 'contrato' },
  { key: 'ejecucion',   label: 'En ejecución', cls: 'ejecucion' },
  { key: 'cobranza',    label: 'Cobranza',     cls: 'cobranza' },
  { key: 'perdido',     label: 'Perdido',      cls: 'perdido' },
  { key: 'cerrado',     label: 'Cobrado',      cls: 'cerrado' },
];

// Calendar node color cycle: azul / morado / verde / naranja (as in client PDF)
const CALENDAR_NODE_COLORS = [
  { bg: 'var(--blueD)',   border: 'var(--blue)',   text: 'var(--blueT)' },
  { bg: 'var(--purpleD)', border: 'var(--purple)', text: 'var(--purpleT)' },
  { bg: 'var(--greenD)',  border: 'var(--green)',  text: 'var(--greenT)' },
  { bg: 'var(--amberD)',  border: 'var(--amber)',  text: 'var(--amberT)' },
];

// Stages sourced from Trello (not Pipedrive) — always show 0 from CRM
const TRELLO_STAGES = ["En ejecución", "Cobranza"];

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

function setPage(name, e) {
  document.querySelectorAll(".page").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".tab").forEach((el) => el.classList.remove("active"));
  document.getElementById("page-" + name).classList.add("active");
  // Use the explicitly passed event (e) — window.event is deprecated and
  // undefined in Firefox (WR-01). Use currentTarget (the element with the
  // listener) not target (which may be a text-node child of the div).
  if (e && e.currentTarget) {
    e.currentTarget.classList.add("active");
  }

  // Load data for the activated tab
  if (name === "overview") {
    loadSummary();
  } else if (name === "funnel") {
    loadFunnel();
  } else if (name === "talent") {
    loadTalentPeriods();   // Fase 7: populate the period dropdown (async, non-blocking)
    loadTalentSelector();
  } else if (name === "leads") {
    loadLeadsSummary();
    loadLeads();
  } else if (name === "reports") {
    loadReportTalents();
    loadReportPeriods();   // Fase 7: populate the won-based month/quarter picker
    loadReportHistory();
  } else if (name === "salud") {
    loadSalud();
  } else if (name === "agent") {
    initAgentTab();
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
        // 6.2: report DEALS updated (Pipedrive), not the Trello card count that
        // the unfiltered /sync/status returns (Trello syncs last). Fall back to
        // the cross-source count if the Pipedrive-specific fetch fails.
        let dealsUpdated = result.records_synced;
        const pdRes = await apiFetch("/sync/status?source=pipedrive");
        if (pdRes && pdRes.ok) {
          const pd = await pdRes.json();
          if (pd && typeof pd.records_synced === "number") {
            dealsUpdated = pd.records_synced;
          }
        }
        showToast(`Sync completado — ${dealsUpdated} deals actualizados`);
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
// Leads overview KPI tiles (D-37 / DASH-04)
// ============================================================

/**
 * Render the "Leads totales" and "Calificados" tiles on the Resumen tab.
 * Uses textContent (not innerHTML) — values are integers, no raw Sheet strings.
 * T-03C-03 mitigated: textContent prevents XSS on these tiles.
 */
function renderLeadsOverviewKpis(leadsTotales, calificados) {
  const totalesEl = document.getElementById("leads-totales-val");
  const calificadosEl = document.getElementById("calificados-val");
  if (totalesEl) totalesEl.textContent = leadsTotales;
  if (calificadosEl) calificadosEl.textContent = calificados;
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
    const trelloBadge = TRELLO_STAGES.includes(stage.stage) ? '<span class="trello-src-badge">vía Trello</span>' : '';
    return `
      <div class="funnel-row">
        <span class="f-label">${escHtml(stage.stage)}${trelloBadge}</span>
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
  if (!res.ok) {
    showToast("Error al cargar el resumen");
    return;
  }

  const data = await res.json();

  // Leads tiles populate on both branches — leads sync independently of Pipedrive deals.
  renderLeadsOverviewKpis(data.leads_totales ?? 0, data.calificados ?? 0);

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
  if (!res.ok) {
    showToast("Error al cargar el funnel");
    return;
  }

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

// SVG icons for talent KPI premium cards
const KPI_ICONS = {
  blue:   `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>`,
  green:  `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
  accent: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
  amber:  `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>`,
  purple: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
};

/**
 * Render KPIs into a specific container as premium talent cards (.kpi-t).
 * Cards with a count show the count as the large number + MXN amount below.
 * Cards without a count show the formatted MXN amount as the large number.
 */
function renderKpisInto(kpis, containerId) {
  const grid = document.getElementById(containerId);
  if (!grid) return;

  if (!kpis || kpis.length === 0) {
    grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin KPIs disponibles</div>`;
    return;
  }

  grid.innerHTML = kpis.map((tile) => {
    const icon = KPI_ICONS[tile.variant] || KPI_ICONS.blue;
    const hasCount = tile.count !== null && tile.count !== undefined;
    const bigVal = hasCount ? tile.count : formatMXN(tile.value);
    const subLabel = hasCount ? "campañas" : "MXN";
    const amountHtml = hasCount
      ? `<div class="kpi-t-amount">${formatMXN(tile.value)}</div>`
      : "";
    // Fase 7/D4: these tiles are a live state, not period-scoped — flag them.
    const isSnapshot = SNAPSHOT_KPI_LABELS.has(tile.label);
    const snapshotHtml = isSnapshot
      ? `<div class="snapshot-tag" title="No se filtra por periodo — refleja el estado actual">Estado actual</div>`
      : "";

    return `
      <div class="kpi-t ${tile.variant}">
        <div class="kpi-t-icon">${icon}</div>
        <div class="kpi-t-label">${escHtml(tile.label)}</div>
        <div class="kpi-t-val">${bigVal}</div>
        <div class="kpi-t-sub">${subLabel}</div>
        ${amountHtml}
        ${snapshotHtml}
      </div>`;
  }).join("");
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

  const total = stages.reduce((s, st) => s + st.count, 0);
  // "Calificados" = Negociación onward (index 2+)
  const calificados = stages.slice(2).reduce((s, st) => s + st.count, 0);
  const pctCal = total > 0 ? Math.round(calificados / total * 100) : 0;

  const header = `
    <div class="funnel-header">
      <div class="fh-stat">
        <div class="fh-val">${total}</div>
        <div class="fh-label">Prospectos</div>
      </div>
      <div class="fh-stat">
        <div class="fh-val" style="color:var(--greenT);">${calificados}</div>
        <div class="fh-label">Calificados</div>
      </div>
      <div class="fh-stat">
        <div class="fh-val" style="color:var(--accent);">${pctCal}%</div>
        <div class="fh-label">% Calificación</div>
      </div>
    </div>`;

  const maxCount = Math.max(...stages.map((s) => s.count), 1);
  const rows = stages.map((stage, idx) => {
    const pct = Math.max((stage.count / maxCount) * 100, stage.count > 0 ? 4 : 0);
    const color = FUNNEL_COLORS[idx % FUNNEL_COLORS.length];
    const countDisplay = stage.count > 0
      ? `<span style="font-size:11px;font-weight:600;color:rgba(255,255,255,0.9);">${stage.count}</span>`
      : "";
    const trelloBadge = TRELLO_STAGES.includes(stage.stage) ? '<span class="trello-src-badge">vía Trello</span>' : '';
    return `
      <div class="funnel-row">
        <span class="f-label">${escHtml(stage.stage)}${trelloBadge}</span>
        <div class="f-track">
          <div class="f-fill" style="width:${pct}%;background:${color};">${countDisplay}</div>
        </div>
        <span class="f-n">${stage.count}</span>
      </div>`;
  }).join("");

  container.innerHTML = header + rows;
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

  // Build conic-gradient stops from percentages.
  // Clamp each stop's end to 100 so that rounding errors (e.g. three slices
  // each at 33.33% summing to 99.99%, or other distributions summing above
  // 100%) never produce invalid CSS stop values (WR-04).
  let conicStops = [];
  let cumPct = 0;
  brandCategories.forEach((slice, idx) => {
    const start = Math.min(cumPct, 100);
    const end = Math.min(cumPct + slice.pct, 100);
    const color = DONUT_COLORS[idx % DONUT_COLORS.length];
    conicStops.push(`${color} ${start}% ${end}%`);
    cumPct += slice.pct;
  });
  // Fill remainder if rounding leaves a gap (guard uses 99.99 to absorb
  // floating-point noise; cumPct is clamped before use).
  if (cumPct < 99.99) {
    conicStops.push(`var(--bg5) ${Math.min(cumPct, 100)}% 100%`);
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

  listEl.innerHTML = ""; // donut replaces list

  if (!lostSummary || lostSummary.length === 0) {
    summaryEl.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">Sin oportunidades perdidas este periodo</div>`;
    return;
  }

  const totalLost = lostSummary.reduce((s, r) => s + r.count, 0);
  let cumPct = 0;
  const conicStops = [];
  lostSummary.forEach((r, i) => {
    const pct = totalLost > 0 ? (r.count / totalLost * 100) : 0;
    const start = Math.min(cumPct, 100);
    const end = Math.min(cumPct + pct, 100);
    conicStops.push(`${DONUT_COLORS[i % DONUT_COLORS.length]} ${start}% ${end}%`);
    cumPct += pct;
  });
  if (cumPct < 99.99) conicStops.push(`var(--bg5) ${Math.min(cumPct,100)}% 100%`);

  const donutCss = `conic-gradient(${conicStops.join(", ")})`;
  const legend = lostSummary.map((r, i) => {
    const pct = totalLost > 0 ? (r.count / totalLost * 100).toFixed(0) : 0;
    return `
      <div style="display:flex;align-items:center;gap:7px;font-size:11px;">
        <div style="width:8px;height:8px;border-radius:50%;background:${DONUT_COLORS[i % DONUT_COLORS.length]};flex-shrink:0;"></div>
        <div style="color:var(--text2);flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escHtml(r.reason)} — ${pct}%</div>
        <div style="font-family:'DM Mono',monospace;font-size:11px;color:var(--text3);">${r.count}</div>
      </div>`;
  }).join("");

  summaryEl.innerHTML = `
    <div class="donut-wrap">
      <div style="width:70px;height:70px;border-radius:50%;background:${donutCss};
        -webkit-mask:radial-gradient(circle,transparent 25px,black 25px);
        mask:radial-gradient(circle,transparent 25px,black 25px);flex-shrink:0;"></div>
      <div class="donut-legend" style="gap:6px;">${legend}</div>
    </div>`;
}

// ============================================================
// Campaign filter helpers
// ============================================================

function dealFilterKey(deal) {
  if (deal.list_state === 'perdido') return 'perdido';
  if (deal.list_state === 'cerrado') return 'cerrado';
  if (deal.list_state === 'cobranza') return 'cobranza';
  // For ejecucion deals, try to resolve from Pipedrive stage_name
  if (deal.stage_name) {
    const s = deal.stage_name.toLowerCase();
    if (s.includes('llamada'))  return 'llamada';
    if (s.includes('cotiz'))    return 'cotizacion';
    if (s.includes('negoci'))   return 'negociacion';
    if (s.includes('contrato')) return 'contrato';
    if (s.includes('ejecuci'))  return 'ejecucion';
    if (s.includes('cobranza')) return 'cobranza';
  }
  return deal.list_state || 'ejecucion';
}

function setCampaignFilter(key) {
  _campaignFilter = key;
  const pillsEl = document.getElementById('campaign-filter-pills');
  if (pillsEl) {
    pillsEl.querySelectorAll('.filter-pill').forEach((p) => {
      const isActive = p.dataset.filter === key;
      const f = CAMPAIGN_FILTERS.find((cf) => cf.key === p.dataset.filter);
      p.className = isActive
        ? `filter-pill active ${f ? f.cls : ''}`.trimEnd()
        : 'filter-pill';
    });
  }
  renderCampaignRows();
}

function setKpiView(view) {
  _kpiView = view;
  const toggleEl = document.getElementById('kpi-toggle');
  if (toggleEl) {
    toggleEl.querySelectorAll('.kpi-toggle-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.view === view);
    });
  }
  if (!_talentDetailData) return;
  if (view === 'flujo') {
    renderKpisInto(_talentDetailData.flujo_dinero || [], 'talent-kpis');
  } else {
    renderKpisInto(_talentDetailData.kpis, 'talent-kpis');
  }
}

function renderCampaignRows() {
  const el = document.getElementById('talent-deals');
  if (!el) return;

  const deals = _campaignDeals || [];
  const lostOpps = _campaignLostOpps || [];
  const activeRows = deals.map((d) => ({ ...d, _src: 'deal' }));
  const lostRows = lostOpps.map((o) => ({
    title: o.title, amount: o.amount, list_state: 'perdido', _src: 'lost',
  }));
  const allRows = [...activeRows, ...lostRows];

  if (allRows.length === 0) {
    el.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:12px 0;">Sin campañas registradas</div>`;
    return;
  }

  const filtered = _campaignFilter === 'all'
    ? allRows
    : allRows.filter((r) => dealFilterKey(r) === _campaignFilter);

  if (filtered.length === 0) {
    el.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:16px 0;">Sin campañas en este estatus</div>`;
    return;
  }

  const header = `
    <div class="ctable-header">
      <div class="ctable-hcol hicon"></div>
      <div class="ctable-hcol hname">Campaña / Marca</div>
      <div class="ctable-hcol hamount">Venta Total</div>
      <div class="ctable-hcol hstatus">Estatus</div>
    </div>`;

  const rows = filtered.map((row) => {
    if (row._src === 'lost') {
      return `
        <div class="ctable-row">
          <div class="ctable-icon" style="background:var(--red)"></div>
          <div class="ctable-name">${escHtml(row.title || 'Sin título')}</div>
          <div class="ctable-amount">${formatMXN(row.amount || 0)}</div>
          <span class="sbadge perdido">Perdido</span>
        </div>`;
    }
    const sb = getDealBadge(row.list_state);
    const color = dealStateColor(row.list_state);
    return `
      <div class="ctable-row">
        <div class="ctable-icon" style="background:${color}"></div>
        <div class="ctable-name">${escHtml(row.title || 'Sin título')}</div>
        <div class="ctable-amount">${formatMXN(row.amount || 0)}</div>
        <span class="sbadge ${sb.cls}">${sb.label}</span>
      </div>`;
  });

  el.innerHTML = header + rows.join('');
}

// ============================================================
// Status badge helper — maps funnel stage name → CSS class + label
// ============================================================

function getStatusBadge(stageName) {
  const s = (stageName || "").toLowerCase();
  if (s.includes("llamada"))   return { cls: "llamada",     label: "Llamada" };
  if (s.includes("negoci"))    return { cls: "negociacion", label: "Negociación" };
  if (s.includes("cotiz"))     return { cls: "cotizacion",  label: "Cotización" };
  if (s.includes("contrato"))  return { cls: "contrato",    label: "Contrato" };
  if (s.includes("cobrado"))   return { cls: "cobrado",     label: "Cobrado" };
  if (s.includes("ejecuci"))   return { cls: "ejecucion",   label: "En ejecución" };
  if (s.includes("cobranza"))  return { cls: "cobranza",    label: "Cobranza" };
  if (s.includes("perdido") || s.includes("lost")) return { cls: "perdido", label: "Perdido" };
  return { cls: "llamada", label: escHtml(stageName) };
}

function statusBadgeColor(cls) {
  const map = {
    llamada: "var(--blue)", negociacion: "var(--amber)", cotizacion: "var(--purple)",
    contrato: "var(--accent)", cobrado: "var(--green)",
    ejecucion: "#0ea5b0", cobranza: "#0d7a55", perdido: "var(--red)",
  };
  return map[cls] || "var(--text3)";
}

// ============================================================
// Talent header
// ============================================================

function renderTalentHeader(name) {
  const wrap = document.getElementById("talent-header-wrap");
  const nameEl = document.getElementById("th-name");
  const dateEl = document.getElementById("th-date");
  if (!wrap || !nameEl || !dateEl) return;
  nameEl.textContent = name || "—";
  const months = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];
  const now = new Date();
  dateEl.textContent = months[now.getMonth()] + " " + now.getFullYear();
  wrap.style.display = "";
}

// ============================================================
// Income projection chart (Phase 4 data source — shows placeholder until wired)
// ============================================================

function renderIncomeProjection(data) {
  const el = document.getElementById("income-projection");
  if (!el) return;
  if (!data || data.length === 0) {
    el.innerHTML = `<div class="proj-placeholder">Proyección disponible tras próxima sincronización</div>`;
    return;
  }
  const maxVal = Math.max(...data.map((m) => (m.cobrado || 0) + (m.proyeccion || 0) + (m.pendiente || 0)), 1);

  // Helper: segment div with label when segment is tall enough to fit text
  const seg = (pctRaw, color, val) => {
    const h = parseFloat(pctRaw);
    const lbl = h > 10 && val > 0
      ? `<span style="font-size:12px;font-family:'DM Mono',monospace;font-weight:700;color:#fff;">${formatMXN(val)}</span>`
      : "";
    return `<div style="height:${h}%;background:${color};display:flex;align-items:center;justify-content:center;overflow:hidden;">${lbl}</div>`;
  };

  const bars = data.map((m) => {
    const total  = (m.cobrado || 0) + (m.proyeccion || 0) + (m.pendiente || 0);
    const pctH   = ((total / maxVal) * 100).toFixed(1);
    const pctC   = ((m.cobrado    || 0) / maxVal * 100).toFixed(1);
    const pctP   = ((m.proyeccion || 0) / maxVal * 100).toFixed(1);
    const pctPe  = ((m.pendiente  || 0) / maxVal * 100).toFixed(1);
    const isCurrent = m.is_current === true;
    const sublabel  = isCurrent ? "(Real)" : "(Estimado)";
    const totalLbl  = total > 0
      ? `<div style="position:absolute;bottom:calc(${pctH}% + 4px);left:0;right:0;text-align:center;font-size:10px;font-family:'DM Mono',monospace;color:var(--text2);white-space:nowrap;">${formatMXN(total)}</div>`
      : "";
    // Empty bar placeholder — subtle dashed outline so the column is visible
    const emptyBar = total === 0
      ? `<div style="height:6px;border-radius:4px 4px 0 0;border:1px dashed var(--text3);opacity:0.4;"></div>`
      : `<div class="proj-bar-stack" style="height:${pctH}%;">${seg(pctC,"var(--green)",m.cobrado||0)}${seg(pctP,"var(--blue)",m.proyeccion||0)}${seg(pctPe,"var(--amber)",m.pendiente||0)}</div>`;
    return `
      <div class="proj-col" style="height:100%;">
        ${totalLbl}
        ${emptyBar}
        <div class="proj-lbl">
          <span class="proj-lbl-month">${escHtml(m.month)}</span>
          <span class="proj-lbl-sub">${sublabel}</span>
        </div>
      </div>`;
  }).join("");
  el.innerHTML = `
    <div class="proj-legend">
      <div class="proj-legend-item"><div class="proj-legend-dot" style="background:var(--green)"></div>Cobrado</div>
      <div class="proj-legend-item"><div class="proj-legend-dot" style="background:var(--blue)"></div>En campaña</div>
      <div class="proj-legend-item"><div class="proj-legend-dot" style="background:var(--amber)"></div>Pendiente</div>
    </div>
    <div class="proj-chart">${bars}</div>`;
}

// ============================================================
// Payment calendar timeline (Phase 4 data source — shows placeholder until wired)
// ============================================================

function renderPaymentCalendar(data) {
  const el = document.getElementById("payment-calendar");
  if (!el) return;
  if (!data || data.length === 0) {
    el.innerHTML = `<div class="tl-placeholder">Calendario disponible tras próxima sincronización</div>`;
    return;
  }
  const nodes = data.map((item, i) => {
    const c = CALENDAR_NODE_COLORS[i % CALENDAR_NODE_COLORS.length];
    const connector = i < data.length - 1
      ? `<div class="tl-connector" style="background:${c.border};opacity:0.25;"></div>`
      : "";
    const abbr = escHtml((item.month || '').substring(0, 3));
    return `
      <div class="tl-node">
        <div class="tl-dot" style="background:${c.bg};border-color:${c.border};">
          <span style="font-size:10px;font-weight:700;font-family:'Sora',sans-serif;color:${c.text};letter-spacing:0;">${abbr}</span>
        </div>
        <div class="tl-month" style="color:${c.text};">${escHtml(item.month)}</div>
        <div class="tl-amount">${formatMXN(item.amount)}</div>
      </div>${connector}`;
  }).join("");
  el.innerHTML = `<div class="timeline">${nodes}</div>`;
}

// ============================================================
// Top 3 campañas — medal cards from individual deal rows (Phase 4)
// ============================================================

/**
 * Map a deal list_state to a badge CSS class and display label.
 * Used for individual deal rows (not funnel stage aggregates).
 * @param {string} listState - ejecucion | cobranza | cerrado | perdido
 * @returns {{cls: string, label: string}}
 */
function getDealBadge(listState) {
  switch (listState) {
    case "ejecucion": return { cls: "ejecucion", label: "En ejecución" };
    case "cobranza":  return { cls: "cobranza",  label: "En cobranza" };
    case "cerrado":   return { cls: "cobrado",   label: "Cobrado" };
    case "perdido":   return { cls: "perdido",   label: "Perdido" };
    default:          return { cls: "ejecucion", label: "En ejecución" };
  }
}

/**
 * Map a deal list_state to an icon color for the ctable-icon dot.
 * @param {string} listState
 * @returns {string} CSS color value
 */
function dealStateColor(listState) {
  switch (listState) {
    case "ejecucion": return "var(--blue)";
    case "cobranza":  return "var(--green)";
    case "cerrado":   return "var(--green)";
    case "perdido":   return "var(--red)";
    default:          return "var(--blue)";
  }
}

/**
 * Render the Top 3 campaigns medal cards from individual deal objects.
 *
 * Phase 4 change: accepts Array<{title, amount, list_state, trello_card_id?}>
 * (individual deal rows) instead of funnel stage aggregates.
 * Sorts by amount descending and takes the top 3.
 * All API-sourced strings are wrapped in escHtml (CR-02 / T-04-11).
 *
 * @param {Array<{title: string, amount: number, list_state: string}>} deals
 */
const MEDAL_CONFIG = [
  { cls: "rank-1", num: "1", color: "#f0a93a", bg: "rgba(240,169,58,0.18)" },
  { cls: "rank-2", num: "2", color: "#b0afa6", bg: "rgba(156,155,146,0.18)" },
  { cls: "rank-3", num: "3", color: "#c97c14", bg: "rgba(201,124,20,0.18)" },
];

function renderTopCampaigns(deals) {
  const el = document.getElementById("top-campaigns");
  if (!el) return;

  const top3 = (deals || [])
    .filter((d) => d.list_state !== "perdido")
    .sort((a, b) => (b.amount || 0) - (a.amount || 0))
    .slice(0, 3);

  if (top3.length === 0) {
    el.innerHTML = `<div class="card" style="text-align:center;color:var(--text3);font-size:13px;padding:14px 16px;">Sin campañas con monto registrado</div>`;
    return;
  }

  el.innerHTML = `<div class="medal-cards">${top3.map((deal, i) => {
    const m = MEDAL_CONFIG[i];
    const sb = getDealBadge(deal.list_state);
    const talento = Math.round((deal.amount || 0) * 0.70);
    return `
      <div class="medal-card ${m.cls}">
        <div class="medal-top">
          <div class="medal-badge-round" style="background:${m.bg};color:${m.color};">${m.num}</div>
          <div class="medal-brand-name">${escHtml(deal.title || "Sin título")}</div>
        </div>
        <span class="sbadge ${sb.cls}">${sb.label}</span>
        <div class="medal-amounts">
          <div class="medal-amt-col">
            <div class="medal-amt-label">Venta total</div>
            <div class="medal-amt-val">${formatMXN(deal.amount || 0)}</div>
          </div>
          <div class="medal-amt-col">
            <div class="medal-amt-label">Talento (70%)</div>
            <div class="medal-amt-val">${formatMXN(talento)}</div>
          </div>
        </div>
      </div>`;
  }).join("")}</div>`;
}

// ============================================================
// Campaign table — individual deal rows (Phase 4)
// ============================================================

/**
 * Render the campaign table from individual deal objects.
 *
 * Phase 4 change: first arg now receives Array<{title, amount, list_state,
 * trello_card_id?}> (individual deal rows) instead of funnel stage aggregates.
 * Lost deals (list_state='perdido') from lostOpps are appended as final rows.
 * All API-sourced strings are wrapped in escHtml (CR-02 / T-04-11).
 *
 * @param {Array<{title: string, amount: number, list_state: string}>} deals
 * @param {Array<{title: string, amount: number, loss_reason: string|null}>} lostOpps
 */
function renderCampaignTable(deals, lostOpps) {
  _campaignDeals = deals || [];
  _campaignLostOpps = lostOpps || [];
  _campaignFilter = 'all'; // reset to Todos on every new talent

  const pillsEl = document.getElementById('campaign-filter-pills');
  if (pillsEl) {
    pillsEl.innerHTML = CAMPAIGN_FILTERS.map((f) =>
      `<button class="filter-pill${f.key === 'all' ? ' active' : ''}"
               data-filter="${f.key}"
               onclick="setCampaignFilter('${f.key}')">${f.label}</button>`
    ).join('');
  }

  renderCampaignRows();
}

/**
 * Load the available won-based periods (months + quarters) and populate the
 * Por Talento period dropdown. Won-based and global (the filter operates on
 * won_time, so only periods with signings are offered). The current period is
 * always ensured present so the D2 default works even with no won deals yet.
 */
async function loadTalentPeriods() {
  const [mRes, qRes] = await Promise.all([
    apiFetch('/reports/months'),
    apiFetch('/reports/quarters'),
  ]);
  if (!mRes || !qRes) return; // 401 redirected
  _talentPeriodLists.months = mRes.ok ? (await mRes.json()) || [] : [];
  _talentPeriodLists.quarters = qRes.ok ? (await qRes.json()) || [] : [];
  populateTalentPeriodSelect();
}

/** Fill #talent-period-select with the options for the active period type. */
function populateTalentPeriodSelect() {
  const sel = document.getElementById('talent-period-select');
  if (!sel) return;

  const isMonth = _talentPeriod.type === 'month';
  const list = isMonth ? _talentPeriodLists.months.slice() : _talentPeriodLists.quarters.slice();
  const current = isMonth ? currentMonthValueJS() : currentQuarterValueJS();
  // Always offer the current period (D2 default) even if it has no won deals.
  if (!list.includes(current)) list.unshift(current);
  // Keep _talentPeriod.value valid for the active type.
  if (!list.includes(_talentPeriod.value)) _talentPeriod.value = current;

  sel.innerHTML = list
    .map((v) => `<option value="${escHtml(v)}"${v === _talentPeriod.value ? ' selected' : ''}>${escHtml(formatPeriodLabel(_talentPeriod.type, v))}</option>`)
    .join('');
}

/** Toggle month/quarter mode, repopulate the dropdown, reload the talent. */
function setTalentPeriodType(type, e) {
  if (type !== 'month' && type !== 'quarter') return;
  _talentPeriod.type = type;
  _talentPeriod.value = type === 'month' ? currentMonthValueJS() : currentQuarterValueJS();

  const toggle = document.getElementById('talent-period-toggle');
  if (toggle) {
    toggle.querySelectorAll('.period-toggle-btn').forEach((b) => {
      b.classList.toggle('active', b.dataset.ptype === type);
    });
  }
  populateTalentPeriodSelect();
  if (_currentTalentId !== null) loadTalentDetail(_currentTalentId);
}

/** Dropdown change → update the selected value and reload the current talent. */
function onTalentPeriodChange() {
  const sel = document.getElementById('talent-period-select');
  if (!sel) return;
  _talentPeriod.value = sel.value;
  if (_currentTalentId !== null) loadTalentDetail(_currentTalentId);
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
  if (!res.ok) {
    showToast("Error al cargar talentos");
    return;
  }

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
           data-talent-id="${talent.talent_id}"
           data-talent-name="${escHtml(talent.name)}">
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
 */
async function loadTalentDetail(talentId) {
  _currentTalentId = talentId;

  // Fase 7: scope the closed metrics to the selected period (D2 default applies).
  const p = _talentPeriod;
  const qs = `?period_type=${encodeURIComponent(p.type)}&period_value=${encodeURIComponent(p.value)}`;
  const showingEl = document.getElementById("talent-period-showing");
  if (showingEl) showingEl.textContent = `Mostrando: ${formatPeriodLabel(p.type, p.value)}`;

  const res = await apiFetch("/dashboard/talents/" + talentId + qs);
  if (!res) return; // 401 redirected

  if (!res.ok) {
    const lostList = document.getElementById("lost-list");
    if (lostList) lostList.innerHTML = `<div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">No se pudo cargar el detalle del talento</div>`;
    return;
  }

  const data = await res.json();

  // Cache for KPI toggle re-renders; reset view to Flujo de dinero on each talent load
  _talentDetailData = data;
  _kpiView = 'flujo';
  const toggleEl = document.getElementById('kpi-toggle');
  if (toggleEl) {
    toggleEl.querySelectorAll('.kpi-toggle-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.view === 'flujo');
    });
  }

  // Talent header — get name from active selector card
  const activeCard = document.querySelector("#talent-selector .talent-card.active");
  const talentName = activeCard ? activeCard.dataset.talentName : null;
  renderTalentHeader(talentName);

  // KPIs — default to Flujo de dinero view
  renderKpisInto(data.flujo_dinero || data.kpis, "talent-kpis");

  // Funnel
  renderTalentFunnel(data.funnel);

  // Projection chart + calendar — placeholder until Phase 4 wires data
  renderIncomeProjection(data.income_projection || null);
  renderPaymentCalendar(data.payment_calendar || null);

  // Brand donut
  renderBrandDonut(data.brand_categories);

  // Lost opportunities (in two-col layout)
  renderLostOpportunities(data.lost_summary, data.lost_opportunities);

  // Top 3 campaigns + full campaign table — Phase 4: use individual deal rows
  // from data.deals (list_state per TrelloCard), not funnel stage aggregates.
  const activeDeals = data.deals || [];
  renderTopCampaigns(activeDeals);
  renderCampaignTable(activeDeals, data.lost_opportunities);
}

// ============================================================
// Initialization
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  loadSyncStatus();
  loadSummary(); // Load Resumen tab on initial page load
});
