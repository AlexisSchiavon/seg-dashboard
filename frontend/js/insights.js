// Insights por IA (Módulo 1 / Resumen). Reuses apiFetch (auth) from auth.js.
// GET /api/insights/resumen → {insights:[{titulo,texto,tipo}], generated_at, cached, error?}

const INSIGHT_ICON = {
  positivo: "▲",
  neutro: "•",
  atencion: "!",
  alerta: "▼",
};

function renderInsightsSkeleton() {
  const c = document.getElementById("insights-container");
  if (!c) return;
  c.innerHTML =
    '<div class="insights-list">' +
    Array(3).fill('<div class="insight-card skeleton"><div class="pdf-skeleton" style="height:14px;width:40%;margin-bottom:8px;"></div><div class="pdf-skeleton" style="height:12px;width:85%;"></div></div>').join("") +
    "</div>";
}

function renderInsights(data) {
  const c = document.getElementById("insights-container");
  const updated = document.getElementById("insights-updated");
  if (!c) return;

  const insights = (data && data.insights) || [];

  if (data && data.error) {
    c.innerHTML = '<div class="card insights-empty">Insights no disponibles temporalmente.</div>';
    if (updated) updated.textContent = "";
    return;
  }
  if (!insights.length) {
    c.innerHTML = '<div class="card insights-empty">Sin insights por ahora.</div>';
    if (updated) updated.textContent = "";
    return;
  }

  c.innerHTML =
    '<div class="insights-list">' +
    insights
      .map((it) => {
        const tipo = ["positivo", "neutro", "atencion", "alerta"].includes(it.tipo) ? it.tipo : "neutro";
        const titulo = escapeInsight(it.titulo || "");
        const texto = escapeInsight(it.texto || "");
        return (
          '<div class="insight-card ' + tipo + '">' +
          '<div class="insight-icon">' + (INSIGHT_ICON[tipo] || "•") + "</div>" +
          '<div class="insight-body">' +
          '<div class="insight-title">' + titulo + "</div>" +
          (texto ? '<div class="insight-text">' + texto + "</div>" : "") +
          "</div></div>"
        );
      })
      .join("") +
    "</div>";

  if (updated) {
    const mins = typeof formatMinutesAgo === "function" ? formatMinutesAgo(data.generated_at) : null;
    updated.textContent = mins ? "Actualizado " + mins : "";
  }
}

function escapeInsight(s) {
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

async function loadInsights(regenerate) {
  const btn = document.getElementById("insights-regen-btn");
  renderInsightsSkeleton();
  if (btn) btn.disabled = true;
  try {
    const path = "/api/insights/resumen" + (regenerate ? "?regenerate=true" : "");
    const res = await apiFetch(path);
    if (res.status === 429) {
      showToast && showToast("Espera un momento antes de regenerar.");
      // keep whatever was there; reload cached view
      const cachedRes = await apiFetch("/api/insights/resumen");
      renderInsights(await cachedRes.json());
      return;
    }
    if (!res.ok) {
      renderInsights({ insights: [], error: "no disponible" });
      return;
    }
    renderInsights(await res.json());
  } catch (e) {
    renderInsights({ insights: [], error: "no disponible" });
  } finally {
    if (btn) btn.disabled = false;
  }
}

function regenerateInsights() {
  loadInsights(true);
}
