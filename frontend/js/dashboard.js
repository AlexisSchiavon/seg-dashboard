// Dashboard shell: tab switching + sync controls.
// Reuses apiFetch (401 -> /login.html redirect) from auth.js — do not redefine.

const SYNC_POLL_INTERVAL_MS = 2000;
const SYNC_POLL_TIMEOUT_MS = 5 * 60 * 1000; // give up polling after 5 minutes

function setPage(name) {
  document.querySelectorAll(".page").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".tab").forEach((el) => el.classList.remove("active"));
  document.getElementById("page-" + name).classList.add("active");
  if (event && event.target) {
    event.target.classList.add("active");
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
      }
      // On status=="error", renderSyncBanner (called via loadSyncStatus in the
      // finally block below) shows the D-24 failure banner — no separate toast.
    }
  } finally {
    btn.textContent = originalLabel;
    btn.disabled = false;
    loadSyncStatus();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadSyncStatus();
});
