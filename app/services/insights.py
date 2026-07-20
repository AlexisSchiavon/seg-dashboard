"""AI-generated executive insights for the Resumen (Módulo 1).

Reuses the existing NL agent (app/services/agent.py) — it does NOT build new
AI. The agent runs its read-only tool loop against real data; we parse its
JSON answer, cache it 1h, and serve it to the dashboard. READ-ONLY: nothing
here writes to any external service.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import InsightsCache
from app.services import agent as agent_service

logger = logging.getLogger(__name__)

CACHE_KEY = "resumen"
CACHE_TTL = timedelta(hours=1)
VALID_TIPOS = frozenset({"positivo", "neutro", "atencion", "alerta"})

INSIGHTS_PROMPT = """Eres un analista comercial senior de una agencia de representación de talento.
Analiza el estado del sistema HOY y devuelve entre 3 y 5 insights ejecutivos
breves (máximo 2 líneas cada uno) que un CEO querría ver al abrir el dashboard.

IMPORTANTE — límite de consultas: haz COMO MÁXIMO 4 consultas con tools, y usa
SOLO datos agregados (KPIs globales, ranking de talentos, embudo/funnel, resumen
de leads). NO consultes talento por talento ni hagas comparaciones que requieran
muchas llamadas. En cuanto tengas datos suficientes, DEJA de usar tools y
responde de inmediato.

Foco (elige lo más relevante que puedas cubrir en ≤4 consultas):
- Estado de firmadas/cerradas y pipeline (KPIs globales).
- Talentos destacados o que necesitan atención (ranking).
- Riesgos del embudo (cuellos de botella, cobranza pesada, deals estancados).
- Algo relevante de los leads entrantes.

REGLA CRÍTICA — distingue SIEMPRE con claridad dos cosas distintas y NUNCA las
mezcles en una misma cifra sin etiquetar:
- REVENUE CERRADO / FIRMADAS: deals GANADOS (status won). Es dinero real. Si
  hablas de comisión, es el 70% de ese valor cerrado.
- PIPELINE ABIERTO: deals AÚN NO ganados (cotización, negociación, etc.). Es
  potencial, NO revenue.
Cada vez que cites un monto, di explícitamente si es "cerrado/firmado/ganado" o
"pipeline (potencial, no cerrado)". Un CEO no debe confundir pipeline con revenue
cerrado. Ejemplo correcto: "Cerrado 2026: $16.5M (124 deals); aparte, pipeline
abierto en negociación: $11.9M (potencial)." Ejemplo PROHIBIDO: sumar o presentar
juntos "$72.9M" sin aclarar que es pipeline, no cerrado.

Considera solo data desde el 1 de enero de 2026. NO inventes números; si un tool
falla u omite un dato, no fabriques ese insight.

Tu respuesta FINAL debe ser ÚNICAMENTE el JSON, sin texto antes ni después, sin
markdown, con esta forma exacta:
{"insights":[{"titulo":"máx 60 chars","texto":"máx 200 chars","tipo":"positivo|neutro|atencion|alerta"}]}"""


def _call_agent(db: Session) -> str:
    """Run the NL agent with the fixed insights prompt; return its raw text.

    Isolated so tests can monkeypatch it without touching Anthropic.
    """
    return agent_service.chat(db, INSIGHTS_PROMPT, [])


def _truncate(text: str, limit: int) -> str:
    """Truncate to <= limit chars, cutting at a word boundary and adding '…'.

    Avoids ugly mid-word cuts in CEO-facing text.
    """
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    space = cut.rfind(" ")
    if space > limit * 0.5:  # only trim to word boundary if it's not too aggressive
        cut = cut[:space]
    return cut.rstrip() + "…"


def _parse_insights_json(raw: str) -> list[dict]:
    """Robustly parse the agent's answer into a list of insight dicts.

    Tolerates ```json fences / surrounding prose by extracting the outermost
    JSON object. Raises (ValueError/JSONDecodeError) if no valid object is
    found — callers treat that as an error and return empty insights.
    """
    if not raw:
        raise ValueError("empty agent response")
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object in agent response")
    data = json.loads(raw[start:end + 1])
    items = data.get("insights", [])
    result: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        titulo = str(it.get("titulo", "")).strip()[:60]
        if not titulo:
            continue
        texto = _truncate(str(it.get("texto", "")), 200)
        tipo = it.get("tipo", "neutro")
        if tipo not in VALID_TIPOS:
            tipo = "neutro"
        result.append({"titulo": titulo, "texto": texto, "tipo": tipo})
    return result


def generate_insights(db: Session) -> list[dict]:
    """Call the agent and parse. Raises on agent/parse failure (caller catches)."""
    raw = _call_agent(db)
    return _parse_insights_json(raw)


def _aware(dt: datetime) -> datetime:
    """SQLite may return naive datetimes; assume UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def get_resumen_insights(db: Session, regenerate: bool = False) -> dict:
    """Return cached insights (< 1h) or regenerate. Never raises: on agent
    failure returns {"insights": [], "error": "no disponible", ...} so the
    Resumen never breaks."""
    now = datetime.now(timezone.utc)
    row = db.query(InsightsCache).filter_by(cache_key=CACHE_KEY).first()

    if not regenerate and row is not None:
        gen = _aware(row.generated_at)
        if now - gen < CACHE_TTL:
            return {
                "insights": json.loads(row.content_json),
                "generated_at": gen.isoformat(),
                "cached": True,
            }

    try:
        insights = generate_insights(db)
    except Exception as exc:  # noqa: BLE001 — insights must never break the Resumen
        logger.warning("insights generation failed: %s", exc)
        return {
            "insights": [],
            "error": "no disponible",
            "generated_at": now.isoformat(),
            "cached": False,
        }

    if row is None:
        row = InsightsCache(cache_key=CACHE_KEY)
        db.add(row)
    row.content_json = json.dumps(insights, ensure_ascii=False)
    row.generated_at = now
    db.commit()
    return {"insights": insights, "generated_at": now.isoformat(), "cached": False}
