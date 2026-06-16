"""Report generation service — orchestrates payload assembly, Claude narrative call,
PDF rendering via WeasyPrint, and Report row upsert.

Design principles (05-CONTEXT.md / STATE.md hard rules):
  - ALL numeric figures in the report come from Python services (kpis, funnel, leads).
    Claude receives a pre-computed JSON payload and ONLY returns 3 prose narrative sections.
  - Claude output is NEVER used for numbers in the PDF appendix or in the payload dict.
  - This module is the ONLY place where the anthropic client and WeasyPrint are imported
    so that conftest.py mock_anthropic and mock_weasyprint fixtures can patch them cleanly.

Security (STRIDE threat register, 05-02-PLAN.md):
  T-path-traversal: _slug(talent) returns str(talent.id) — purely numeric, no separators.
  T-ssrf: _render_pdf passes the literal string "." as base_url to WeasyPrint — never a
    user-controlled value.
  T-claude-numbers: All KPI/funnel figures in the PDF come from Python; Claude prose is
    used only for the 3 narrative sections.
"""
import json
import os
import re
from datetime import datetime

import anthropic
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Deal, Report, Talent

# HTML is imported lazily inside _render_pdf() to avoid failing on macOS/CI environments
# that lack Pango/Cairo system libs. monkeypatch fixtures patch this module-level name
# (app.services.reports.HTML) so tests work without system libraries.
HTML = None  # replaced by mock_weasyprint in tests; lazy-imported in _render_pdf
from app.services import funnel as funnel_service
from app.services import kpis as kpi_service
from app.services import leads as leads_service

# Jinja2 environment — autoescape=True to HTML-escape all Jinja2 variables,
# including Claude-generated prose (protects against XSS in any future web rendering).
_jinja_env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=True,
)

SYSTEM_PROMPT = (
    "Eres un analista de inteligencia comercial para Santillán Entertainment Group, "
    "una agencia de talentos/influencers en México. "
    "El usuario te proporcionará un JSON con cifras ya calculadas por Python. "
    "Debes usar ÚNICAMENTE los números del JSON proporcionado. "
    "NUNCA inventes cifras, porcentajes ni fechas. "
    "NUNCA calcules totales ni promedios por tu cuenta. "
    "Responde ÚNICAMENTE con un JSON válido con exactamente tres claves: "
    '"resumen_ejecutivo", "deals_destacados", "recomendacion". '
    "Cada valor debe ser una cadena de texto en español con tu análisis narrativo. "
    "No incluyas bloques de código ni marcadores markdown — solo el JSON plano."
)


def available_months(db: Session, talent_id: int) -> list[str]:
    """Return distinct YYYY-MM strings from Deal.add_time for this talent, descending.

    Excludes rows where add_time is None or whose [:7] slice does not match r'\\d{4}-\\d{2}'.
    Returns [] if no deals exist for the given talent_id.
    """
    rows = (
        db.query(Deal.add_time)
        .filter(Deal.talent_id == talent_id, Deal.add_time.isnot(None))
        .all()
    )

    months: set[str] = set()
    for (add_time,) in rows:
        if add_time is None:
            continue
        m = add_time[:7]
        if re.fullmatch(r"\d{4}-\d{2}", m):
            months.add(m)

    return sorted(months, reverse=True)


def _build_payload(db: Session, talent: Talent, month: str) -> dict:
    """Assemble the Python-computed figures dict to pass to Claude.

    ALL numeric values in this dict come from the kpis/funnel/leads service layer.
    No ORM instances are placed in the returned dict — it must be JSON-serializable.
    """
    # KPIs from kpi_service.talent_detail
    try:
        detail = kpi_service.talent_detail(db, talent.id)
    except ValueError:
        detail = {
            "kpis": [],
            "funnel": [],
            "lost_summary": [],
            "lost_opportunities": [],
            "brand_categories": [],
        }

    # Extract scalar KPIs from the kpis list by label
    kpis_list = detail.get("kpis", [])
    kpi_by_label: dict[str, dict] = {k["label"]: k for k in kpis_list}

    pipeline_val = kpi_by_label.get("Pipeline", {}).get("value", 0.0)
    cerrados_count = kpi_by_label.get("Cerrados", {}).get("count", 0)
    cerrados_valor = kpi_by_label.get("Cerrados", {}).get("value", 0.0)
    comision = kpi_by_label.get("Comisión", {}).get("value", 0.0)

    # Funnel stages (list of {stage, count, amount} dicts — already plain scalars)
    funnel_stages = funnel_service.talent_funnel(db, talent.id)

    # Top 3 open deals by value for this talent
    top_deals_rows = (
        db.query(Deal.title, Deal.value, Deal.stage_name)
        .filter(Deal.talent_id == talent.id, Deal.status == "open")
        .order_by(desc(Deal.value))
        .limit(3)
        .all()
    )
    top_deals = [
        {"title": row[0], "value": float(row[1]), "stage_name": row[2]}
        for row in top_deals_rows
    ]

    # Global leads counts
    leads_summary = leads_service.leads_summary(db)
    leads_totales = leads_summary["leads_totales"]
    leads_calificados = leads_summary["calificados"]

    # Per-talent leads count
    leads_by_talent = leads_service.leads_by_talent(db)
    talent_leads = next(
        (row for row in leads_by_talent if row.get("talent_id") == talent.id),
        {"total": 0, "calificados": 0},
    )

    return {
        "talent_name": talent.name,
        "month": month,
        "kpis": {
            "pipeline": float(pipeline_val),
            "cerrados_count": int(cerrados_count) if cerrados_count is not None else 0,
            "cerrados_valor": float(cerrados_valor),
            "comision": float(comision),
        },
        "funnel": [
            {
                "stage": s["stage"],
                "count": int(s["count"]),
                "amount": float(s["amount"]),
            }
            for s in funnel_stages
        ],
        "top_deals": top_deals,
        "leads_totales": int(leads_totales),
        "leads_calificados": int(leads_calificados),
        "talent_leads_totales": int(talent_leads.get("total", 0)),
        "talent_leads_calificados": int(talent_leads.get("calificados", 0)),
    }


def _call_claude(payload: dict) -> dict:
    """Call claude-sonnet-4-6 and parse the 3-section JSON response.

    Returns a dict with exactly 3 keys: resumen_ejecutivo, deals_destacados, recomendacion.
    Strips markdown code fences if present (RESEARCH.md Pitfall 2).
    Raises ValueError("Claude returned non-JSON") on parse failure.
    """
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Genera el reporte:\n{json.dumps(payload, ensure_ascii=False)}",
            }
        ],
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown fences if Claude wraps the JSON (Pitfall 2)
    if raw_text.startswith("```"):
        # Remove leading fence (```json or ```)
        raw_text = re.sub(r"^```[a-z]*\n?", "", raw_text)
        # Remove trailing fence
        raw_text = re.sub(r"\n?```$", "", raw_text.rstrip())

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("Claude returned non-JSON") from exc

    return parsed


def _slug(talent: Talent) -> str:
    """Return a filesystem-safe slug for the talent.

    Uses str(talent.id) — purely numeric, no path separators, no Unicode issues.
    Defends T-path-traversal: numeric IDs cannot contain '../' or special characters.
    """
    return str(talent.id)


def _render_pdf(html_str: str, output_path: str) -> int:
    """Render HTML to PDF via WeasyPrint. Returns file size in bytes.

    Uses atomic write: writes to a .tmp file then os.replace() to the final path
    (RESEARCH.md Pitfall 4 — prevents a corrupt/partial file being visible in the DB).

    base_url is the literal string "." — NEVER a user-controlled value (T-ssrf defense).

    HTML is resolved via the module-level name `HTML` (patched to a mock in tests,
    or lazy-imported from weasyprint in production to avoid import-time failures
    on systems without Pango/Cairo system libs).
    """
    global HTML  # noqa: PLW0603
    if HTML is None:
        from weasyprint import HTML as _HTML  # lazy import — only when actually rendering
        HTML = _HTML

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tmp_path = output_path + ".tmp"
    HTML(string=html_str, base_url=".").write_pdf(tmp_path)
    os.replace(tmp_path, output_path)
    return os.path.getsize(output_path)


def generate_report(db: Session, talent_id: int, month: str) -> dict:
    """Orchestrate: build payload → call Claude → render PDF → upsert Report row.

    Returns a dict matching the ReportOut schema shape, including a 'narrative' sub-dict.
    Raises ValueError(f"Talent {talent_id} not found") if the talent doesn't exist.
    Raises ValueError("Claude returned non-JSON") if Claude's response cannot be parsed.
    """
    talent = db.get(Talent, talent_id)
    if talent is None:
        raise ValueError(f"Talent {talent_id} not found")

    # 1. Build Python-computed payload
    payload = _build_payload(db, talent, month)

    # 2. Call Claude for 3 narrative prose sections
    narrative = _call_claude(payload)

    # 3. Render HTML → PDF
    template = _jinja_env.get_template("reports/template.html")
    html_str = template.render(
        talent_name=talent.name,
        month=month,
        narrative=narrative,
        data=payload,
    )
    file_path = f"reports/{_slug(talent)}/{month}.pdf"
    file_size_bytes = _render_pdf(html_str, file_path)

    # 4. Upsert Report row (upsert semantics: overwrite if same talent_id+month exists)
    existing = (
        db.query(Report)
        .filter(Report.talent_id == talent_id, Report.month == month)
        .first()
    )
    if existing is not None:
        existing.file_path = file_path
        existing.file_size_bytes = file_size_bytes
        existing.generated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        report = existing
    else:
        report = Report(
            talent_id=talent_id,
            month=month,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            generated_at=datetime.utcnow(),
        )
        db.add(report)
        db.commit()
        db.refresh(report)

    return {
        "id": report.id,
        "talent_id": report.talent_id,
        "talent_name": talent.name,
        "month": report.month,
        "generated_at": report.generated_at,
        "file_path": report.file_path,
        "file_size_bytes": report.file_size_bytes,
        "narrative": narrative,
    }


def list_reports(db: Session) -> list[dict]:
    """Return all Report rows ordered by generated_at desc, with talent_name resolved.

    Each entry matches the ReportHistoryItem schema shape.
    """
    reports = (
        db.query(Report)
        .order_by(desc(Report.generated_at))
        .all()
    )

    result = []
    for report in reports:
        talent = db.get(Talent, report.talent_id)
        talent_name = talent.name if talent is not None else "Sin talento"
        result.append(
            {
                "id": report.id,
                "talent_id": report.talent_id,
                "talent_name": talent_name,
                "month": report.month,
                "generated_at": report.generated_at,
                "file_size_bytes": report.file_size_bytes,
            }
        )

    return result
