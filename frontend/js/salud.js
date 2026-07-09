// Salud de datos (Prompt 3, Feature 2) — data-health cards + drawer.

const SEVERITY_COLOR = { alta: "#ef4444", media: "#f59e0b", baja: "#10b981" };

function fmtMoneySalud(v) {
  if (!v) return "";
  return "$" + Math.round(v).toLocaleString("es-MX") + " MXN";
}

function sparklineSvg(trend) {
  if (!trend || trend.length < 2) return "";
  const w = 90, h = 26, pad = 2;
  const max = Math.max(...trend, 1);
  const step = (w - pad * 2) / (trend.length - 1);
  const pts = trend
    .map((v, i) => `${(pad + i * step).toFixed(1)},${(h - pad - (v / max) * (h - pad * 2)).toFixed(1)}`)
    .join(" ");
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    <polyline points="${pts}" fill="none" stroke="#60a5fa" stroke-width="1.5"/></svg>`;
}

async function loadSalud() {
  const grid = document.getElementById("salud-grid");
  grid.innerHTML = '<div class="muted">Cargando…</div>';
  try {
    const res = await apiFetch("/api/health");
    if (!res.ok) throw new Error("http " + res.status);
    const data = await res.json();
    grid.innerHTML = "";
    data.checks.forEach((c) => grid.appendChild(renderSaludCard(c)));
  } catch (err) {
    grid.innerHTML =
      '<div class="muted">No se pudo cargar la salud de datos. Intenta de nuevo.</div>';
  }
}

function renderSaludCard(c) {
  const el = document.createElement("div");
  el.className = "salud-card card";
  const dot = SEVERITY_COLOR[c.severity] || "#94a3b8";
  const value = c.affected_value ? `<div class="salud-value">${fmtMoneySalud(c.affected_value)}</div>` : "";
  const delta =
    c.resolved_delta != null && c.resolved_delta !== 0
      ? `<span class="salud-delta ${c.resolved_delta > 0 ? "up" : "down"}">${
          c.resolved_delta > 0 ? "▲ +" + c.resolved_delta : "▼ " + c.resolved_delta
        }</span>`
      : "";
  el.innerHTML = `
    <div class="salud-card-top">
      <span class="salud-sev" style="background:${dot}"></span>
      <div class="salud-title">${c.human_title}</div>
    </div>
    <div class="salud-count-row">
      <div class="salud-count">${c.count}</div>
      ${sparklineSvg(c.trend_24h)}
    </div>
    ${value}
    <div class="salud-desc">${c.description}</div>
    <div class="salud-foot">
      <span class="salud-badge">Depende de tu equipo</span>
      ${delta}
    </div>`;
  el.onclick = () => openSaludDrawer(c.check_id, c.human_title);
  return el;
}

async function openSaludDrawer(checkId, title) {
  document.getElementById("salud-drawer-title").textContent = title;
  const body = document.getElementById("salud-drawer-items");
  const sub = document.getElementById("salud-drawer-sub");
  body.innerHTML = '<div class="muted">Cargando…</div>';
  sub.textContent = "";
  document.getElementById("salud-drawer-overlay").classList.add("open");
  try {
    const res = await apiFetch(`/api/health/${encodeURIComponent(checkId)}/items?limit=200`);
    if (!res.ok) throw new Error("http " + res.status);
    const data = await res.json();
    sub.textContent = `${data.total} caso${data.total === 1 ? "" : "s"} · click en un link para resolver en Pipedrive/Trello`;
    if (!data.items.length) {
      body.innerHTML = '<div class="muted">Sin casos. ✅</div>';
      return;
    }
    body.innerHTML = data.items
      .map((it) => {
        const links = [];
        if (it.link_pipedrive)
          links.push(`<a href="${it.link_pipedrive}" target="_blank" rel="noopener">Pipedrive</a>`);
        if (it.link_trello)
          links.push(`<a href="${it.link_trello}" target="_blank" rel="noopener">Trello</a>`);
        const val = it.value ? `<span class="drawer-item-val">${fmtMoneySalud(it.value)}</span>` : "";
        return `<div class="drawer-item">
          <div class="drawer-item-main">
            <div class="drawer-item-title">${escapeHtmlSalud(it.title || it.id_ref)}</div>
            <div class="drawer-item-links">${links.join(" · ")}</div>
          </div>${val}</div>`;
      })
      .join("");
  } catch (err) {
    body.innerHTML = '<div class="muted">No se pudieron cargar los casos.</div>';
  }
}

function closeSaludDrawer(e) {
  if (e && e.target && e.target.id !== "salud-drawer-overlay") return;
  document.getElementById("salud-drawer-overlay").classList.remove("open");
}

function escapeHtmlSalud(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}
