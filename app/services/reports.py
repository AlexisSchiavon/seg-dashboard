"""Report generation service — assembles the data-driven PDF report (Fase 9).

Fase 9 (D8): the report is 100% Python-computed — there is NO Claude narrative.
All figures come from the same services the "Por Talento" dashboard tab consumes
(kpis, funnel, trello), rendered into Jinja templates + inline SVG charts and
converted to PDF by WeasyPrint.

Security (STRIDE threat register, 05-02-PLAN.md):
  T-path-traversal: _slug(talent) returns str(talent.id) — purely numeric, no separators.
  T-ssrf: _render_pdf passes the literal string "." as base_url to WeasyPrint — never a
    user-controlled value.
"""
import os
import re
from datetime import date, datetime

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import Deal, Report, Talent
from app.services import kpis as kpi_service
from app.services import periods as periods_service
from app.services import report_charts
from app.services import trello_service

# HTML is imported lazily inside _render_pdf() to avoid failing on macOS/CI environments
# that lack Pango/Cairo system libs. monkeypatch fixtures patch this module-level name
# (app.services.reports.HTML) so tests work without system libraries.
HTML = None  # replaced by mock_weasyprint in tests; lazy-imported in _render_pdf

_MONTHS_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

# Jinja2 environment — autoescape=True to HTML-escape all Jinja2 variables.
_jinja_env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=True,
)
# Currency filters shared by the report templates.
#   |mxn      -> compact "$1.2M" / "$50K" / "$0"  (matches dashboard formatMXN)
#   |mxn_full -> "$1,234,567" full pesos with thousands separators
_jinja_env.filters["mxn"] = report_charts._fmt_mxn
_jinja_env.filters["mxn_full"] = lambda v: f"${float(v or 0):,.0f}"


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
    try:
        HTML(string=html_str, base_url=".").write_pdf(tmp_path)
        os.replace(tmp_path, output_path)
    except Exception:
        # WR-03: clean up the .tmp file so it does not linger on disk when WeasyPrint fails
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    return os.path.getsize(output_path)


def generate_report(
    db: Session,
    talent_id: int,
    period_value: str,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    """Generate a single-talent data-driven PDF (Fase 9 — no Claude) and upsert its row.

    period_value is the period label ("YYYY-MM" or "YYYY-QN"), used as the report
    identifier (filename, Report.month, upsert key). start/end are the inclusive
    period bounds for the won_time-scoped figures; when omitted they are derived
    from period_value (month vs quarter inferred from "Q").

    Returns a dict matching the ReportOut schema shape (no narrative — D8).
    Raises ValueError(f"Talent {talent_id} not found") if the talent doesn't exist.
    """
    talent = db.get(Talent, talent_id)
    if talent is None:
        raise ValueError(f"Talent {talent_id} not found")

    if start is None or end is None:
        period_type = "quarter" if "Q" in period_value else "month"
        start, end = periods_service.parse_period(period_type, period_value)

    # Assemble the full document context (cover + one talent page) and render it.
    ctx = build_report_context(db, [talent], period_value, start, end)
    html_str = render_report_html(ctx)
    file_path = f"reports/{_slug(talent)}/{period_value}.pdf"
    file_size_bytes = _render_pdf(html_str, file_path)

    # Upsert Report row (overwrite if same talent_id+period exists). The `month`
    # column stores the period label (also "YYYY-QN" for quarters).
    existing = (
        db.query(Report)
        .filter(Report.talent_id == talent_id, Report.month == period_value)
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
            month=period_value,
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


# =============================================================================
# Fase 9.4 — Redesigned data-driven report (no Claude narrative, D8).
# These assembly helpers reuse the SAME services the "Por Talento" dashboard tab
# consumes, so the PDF is a 1:1 data match (D1). They do NOT touch the DB.
# =============================================================================


def filename_slug(name: str) -> str:
    """Filesystem/URL-safe slug: lowercase, accents stripped, hyphen-separated.

    'Emicánico Pérez' -> 'emicanico-perez'. Empty/garbage collapses to 'talento'.
    """
    import unicodedata

    normalized = unicodedata.normalize("NFKD", name or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return slug or "talento"


def _period_label(period_value: str) -> str:
    """'2026-06' -> 'Junio 2026'; '2026-Q2' -> 'Q2 2026'; passthrough otherwise."""
    m = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", period_value or "")
    if m:
        return f"{_MONTHS_ES[int(m.group(2)) - 1]} {m.group(1)}"
    q = re.fullmatch(r"(\d{4})-Q([1-4])", period_value or "")
    if q:
        return f"Q{q.group(2)} {q.group(1)}"
    return period_value or ""


def _format_won_date(iso_str: str | None) -> str:
    """ISO 'YYYY-MM-DDThh:mm:ss' -> 'D mmm YYYY' in Spanish (e.g. '15 jun 2026')."""
    if not iso_str:
        return "—"
    try:
        d = datetime.fromisoformat(iso_str.replace("Z", "").split("T")[0])
    except ValueError:
        return "—"
    return f"{d.day} {_MONTHS_ES[d.month - 1][:3].lower()} {d.year}"


def build_talent_report(db: Session, talent: Talent, start: date, end: date) -> dict:
    """Assemble one talent's full widget dataset + pre-rendered SVG charts.

    Data sources (identical to app/routers/dashboard.py get_talent_detail):
      - kpi_service.flujo_dinero_kpis  -> 3 headline tiles (firmadas/cobrado/pendiente)
      - kpi_service.talent_detail      -> Pipeline/Cerrados/Comisión, funnel, lost_summary
      - trello_service.income_projection / payment_calendar / deals_for_talent
      - kpi_service.deals_won_in_period -> detailed "deals firmados en el periodo" list
    """
    flujo = kpi_service.flujo_dinero_kpis(db, talent.id, start=start, end=end)
    detail = kpi_service.talent_detail(db, talent.id, start=start, end=end)
    projection = trello_service.income_projection(db, talent.id) or []
    calendar = trello_service.payment_calendar(db, talent.id) or []
    active_deals = trello_service.deals_for_talent(db, talent.id) or []
    won = kpi_service.deals_won_in_period(db, start.isoformat(), end.isoformat(), talent.id)

    # Top 3 active campaigns by amount (exclude lost), mirrors renderTopCampaigns.
    top_deals = sorted(
        (d for d in active_deals if d.get("list_state") != "perdido"),
        key=lambda d: d.get("amount") or 0.0,
        reverse=True,
    )[:3]

    signed = [
        {
            "title": d["title"],
            "date": _format_won_date(d.get("won_time")),
            "value": d["value"],
            "talent_name": d.get("talent_name", talent.name),
        }
        for d in won["deals"]
    ]

    return {
        "talent_name": talent.name,
        "slug": filename_slug(talent.name),
        "headline_kpis": flujo["kpis"],
        "detail_kpis": detail["kpis"],
        "funnel": detail["funnel"],
        "lost_summary": detail["lost_summary"],
        "projection": projection,
        "calendar": calendar,
        "top_deals": top_deals,
        "signed_deals": signed,
        "signed_total": won["total_value"],
        # Pre-rendered SVG charts (D5) — markupsafe.Markup, inlined verbatim by Jinja.
        "funnel_svg": report_charts.funnel_chart_svg(detail["funnel"]),
        "projection_svg": report_charts.projection_bar_chart_svg(projection),
        "donut_svg": report_charts.lost_donut_svg(detail["lost_summary"]),
    }


def build_report_context(
    db: Session,
    talents: list[Talent],
    period_value: str,
    start: date,
    end: date,
) -> dict:
    """Build the full document context (cover + one page per talent).

    Single talent -> cover shows that talent's name and headline KPIs.
    Multiple talents ('all') -> cover title is 'Reporte consolidado' and the
    headline KPIs are summed across talents (D2/D7).
    """
    talent_reports = [build_talent_report(db, t, start, end) for t in talents]

    is_consolidated = len(talents) > 1
    if is_consolidated:
        title = "Reporte consolidado"
        # Sum each headline KPI across talents, preserving label/variant/count.
        cover_kpis = _aggregate_headline_kpis(talent_reports)
    else:
        title = talents[0].name if talents else "Reporte"
        cover_kpis = talent_reports[0]["headline_kpis"] if talent_reports else []

    now = datetime.utcnow()
    return {
        "title": title,
        "is_consolidated": is_consolidated,
        "period_label": _period_label(period_value),
        "period_value": period_value,
        "cover_kpis": cover_kpis,
        "talents": talent_reports,
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "generated_stamp": now.strftime("%Y-%m-%d %H:%M UTC"),
    }


def render_report_html(ctx: dict) -> str:
    """Render the full multi-page report HTML (cover + one page per talent)."""
    return _jinja_env.get_template("reports/base.html").render(ctx=ctx)


def _aggregate_headline_kpis(talent_reports: list[dict]) -> list[dict]:
    """Sum the 3 headline KPI tiles across talents for the consolidated cover."""
    if not talent_reports:
        return []
    template = talent_reports[0]["headline_kpis"]
    agg = []
    for idx, tile in enumerate(template):
        total_value = sum(tr["headline_kpis"][idx]["value"] for tr in talent_reports)
        counts = [tr["headline_kpis"][idx].get("count") for tr in talent_reports]
        total_count = (
            sum(c for c in counts if c is not None)
            if any(c is not None for c in counts)
            else None
        )
        agg.append(
            {
                "label": tile["label"],
                "variant": tile["variant"],
                "value": float(total_value),
                "count": total_count,
            }
        )
    return agg
