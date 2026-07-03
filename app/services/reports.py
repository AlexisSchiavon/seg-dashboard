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
import hashlib
import re
from datetime import date, datetime, timedelta

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import Deal, Report, Talent, TrelloCard
from app.services import kpis as kpi_service
from app.services import periods as periods_service
from app.services import report_charts

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
# |mxn_headline -> compact "$1.67M" for >= 1M (avoids wrapping in the firmadas
# sublabel), full "$557,900" otherwise. Used only on "Valor total en tu 70%".
_jinja_env.filters["mxn_headline"] = lambda v: (
    f"${float(v or 0) / 1_000_000:.2f}M" if float(v or 0) >= 1_000_000
    else f"${float(v or 0):,.0f}"
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


def _render_pdf_bytes(html_str: str) -> bytes:
    """Render HTML to an in-memory PDF via WeasyPrint (Fase 9.5 — no disk file).

    base_url is the literal string "." — NEVER a user-controlled value (T-ssrf
    defense). "." resolves relative asset URLs (the Inter @font-face) against the
    process CWD, which is the project root both locally and in the container.

    HTML is resolved via the module-level name `HTML` (patched to a mock in tests,
    or lazy-imported from weasyprint in production to avoid import-time failures on
    systems without Pango/Cairo system libs).
    """
    global HTML  # noqa: PLW0603
    if HTML is None:
        from weasyprint import HTML as _HTML  # lazy import — only when actually rendering
        HTML = _HTML

    return HTML(string=html_str, base_url=".").write_pdf()


def _resolve_talents(db: Session, talent_ids: "list[int] | str") -> list[Talent]:
    """Resolve the report target into an ordered list of Talent rows.

    talent_ids is either the literal "all" (every active talent, name-sorted) or a
    list of talent ids. Raises ValueError(f"Talent {id} not found") on a bad id.
    """
    if talent_ids == "all":
        return (
            db.query(Talent)
            .filter(Talent.active.is_(True))
            .order_by(Talent.name)
            .all()
        )
    talents: list[Talent] = []
    for tid in talent_ids:
        talent = db.get(Talent, tid)
        if talent is None:
            raise ValueError(f"Talent {tid} not found")
        talents.append(talent)
    return talents


def _talent_ids_label(talent_ids: "list[int] | str", talents: list[Talent]) -> str:
    """The stored regenerate key: "all" or a comma-joined list of talent ids."""
    if talent_ids == "all":
        return "all"
    return ",".join(str(t.id) for t in talents)


def generate_report_pdf(
    db: Session,
    talent_ids: "list[int] | str",
    period_value: str,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    """Render the report PDF in memory and upsert its metadata row (Fase 9.5).

    talent_ids: "all" (consolidated over every active talent) or a list of ids
    (single or multi). period_value is the period label ("YYYY-MM" / "YYYY-QN").

    The PDF is NOT written to disk — it is returned as bytes for streaming and can
    be regenerated later from the stored row (regenerate_report_pdf). The row keeps
    only metadata: talent_ids label, single talent_id (None when consolidated),
    month, byte size, and the content sha256.

    Returns {report_id, filename, pdf_bytes, content_hash, file_size_bytes,
             talent_ids, talent_id, month, is_consolidated}.
    Raises ValueError if a talent id is unknown or the target resolves to empty.
    """
    talents = _resolve_talents(db, talent_ids)
    if not talents:
        raise ValueError("No talents to report")

    if start is None or end is None:
        period_type = "quarter" if "Q" in period_value else "month"
        start, end = periods_service.parse_period(period_type, period_value)

    ctx = build_report_context(db, talents, period_value, start, end)
    pdf_bytes = _render_pdf_bytes(render_report_html(ctx))
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
    file_size_bytes = len(pdf_bytes)

    ids_label = _talent_ids_label(talent_ids, talents)
    is_consolidated = ctx["is_consolidated"]
    # Single owning talent only when exactly one target talent (keeps the FK/history
    # link); consolidated reports store talent_id = None.
    single_talent_id = talents[0].id if (talent_ids != "all" and len(talents) == 1) else None

    if is_consolidated:
        filename = f"reporte-consolidado-{period_value}.pdf"
    else:
        filename = f"reporte-{filename_slug(talents[0].name)}-{period_value}.pdf"

    # Upsert overwrites in place. Single-talent rows are keyed on (talent_id, month)
    # — the table's unique constraint — so a legacy row (talent_ids NULL) is reused
    # instead of colliding. Consolidated rows (talent_id NULL) key on (talent_ids,
    # month), since SQLite treats NULL talent_id as distinct.
    if single_talent_id is not None:
        existing = (
            db.query(Report)
            .filter(Report.talent_id == single_talent_id, Report.month == period_value)
            .first()
        )
    else:
        existing = (
            db.query(Report)
            .filter(Report.talent_ids == ids_label, Report.month == period_value)
            .first()
        )
    if existing is not None:
        existing.talent_id = single_talent_id
        existing.file_path = None
        existing.file_size_bytes = file_size_bytes
        existing.content_hash = content_hash
        existing.generated_at = datetime.utcnow()
        report = existing
    else:
        report = Report(
            talent_id=single_talent_id,
            talent_ids=ids_label,
            month=period_value,
            file_path=None,
            file_size_bytes=file_size_bytes,
            content_hash=content_hash,
            generated_at=datetime.utcnow(),
        )
        db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "report_id": report.id,
        "filename": filename,
        "pdf_bytes": pdf_bytes,
        "content_hash": content_hash,
        "file_size_bytes": file_size_bytes,
        "talent_ids": ids_label,
        "talent_id": single_talent_id,
        "month": period_value,
        "is_consolidated": is_consolidated,
    }


def regenerate_report_pdf(db: Session, report: Report) -> tuple[bytes, str]:
    """Re-render a stored report's PDF on demand (Fase 9.5 — no disk persistence).

    Reconstructs the target from the row's talent_ids label and period (month),
    re-renders, and returns (pdf_bytes, filename). Raises ValueError if a talent
    referenced by the row no longer exists.
    """
    label = report.talent_ids
    if label == "all":
        talent_ids: "list[int] | str" = "all"
    elif label:
        talent_ids = [int(x) for x in label.split(",") if x]
    elif report.talent_id is not None:
        # Legacy row created before talent_ids existed — fall back to the FK.
        talent_ids = [report.talent_id]
    else:
        raise ValueError("Report row has no talent target to regenerate")

    result = generate_report_pdf(db, talent_ids, report.month)
    return result["pdf_bytes"], result["filename"]


def list_reports(db: Session) -> list[dict]:
    """Return all Report rows ordered by generated_at desc, with talent_name resolved.

    Consolidated rows (talent_id is None) are labelled "Consolidado". Each entry
    matches the ReportHistoryItem schema shape.
    """
    reports = (
        db.query(Report)
        .order_by(desc(Report.generated_at))
        .all()
    )

    result = []
    for report in reports:
        if report.talent_id is None:
            talent_name = "Consolidado"
        else:
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


def _signed_deal_estado(card: "TrelloCard | None", start: date, end: date) -> tuple[str, str]:
    """Badge (css class, label) for a signed deal, aligned to the KPI semantics (P3).

    'Cobrado' is shown ONLY when the card is 'cerrado' AND its collection_date is
    within the report month — matching the "Cobrado este mes" KPI. A deal collected
    in a different month reads 'En ejecución', not 'Cobrado', so the table total no
    longer contradicts the headline KPI.
    """
    if card is None:
        return "firmado", "Firmado"
    if card.list_state == "cerrado":
        if card.collection_date and start <= card.collection_date <= end:
            return "cobrado", "Cobrado"
        return "ejecucion", "En ejecución"  # collected in a different month
    if card.list_state == "cobranza":
        return "cobranza", "Por cobrar"
    return "ejecucion", "En ejecución"


def _talent_projection_70(db: Session, talent: Talent) -> list[dict]:
    """Forward-only 4-month projection of the talent's 70% still to be collected (P4).

    Same universe as account_status 'proximos_meses' — ejecucion/cobranza cards
    whose resolved collection_date is today or later — bucketed by month. This keeps
    the projection bars consistent with the "por cobrar próximos meses" tile (a card
    due earlier this month is overdue, not projected).
    """
    import calendar

    from app.services.trello_service import _sliding_window_months, resolve_collection_date

    today = date.today()
    window = _sliding_window_months(today)
    labels = [f"{calendar.month_abbr[d.month]} {d.year}" for d in window]
    sums = {lbl: 0.0 for lbl in labels}

    # 9.8f: only WON deals (keeps this consistent with account_status 'proximos_meses',
    # which the P4 invariant requires; open/lost deals are not projected income).
    rows = (
        db.query(TrelloCard, Deal)
        .join(Deal, TrelloCard.deal_id == Deal.id)
        .filter(Deal.talent_id == talent.id, Deal.status == "won")
        .all()
    )
    for card, deal in rows:
        if card.list_state not in ("ejecucion", "cobranza"):
            continue
        resolved = card.collection_date or resolve_collection_date(None, deal)
        if resolved < today:
            continue  # overdue, not projected (P4 — align with proximos_meses)
        lbl = f"{calendar.month_abbr[resolved.month]} {resolved.year}"
        if lbl in sums:
            sums[lbl] += kpi_service._talent_70(deal)

    return [
        {"month": lbl, "estimado70": sums[lbl], "is_current": i == 0,
         "has_data": sums[lbl] > 0}
        for i, lbl in enumerate(labels)
    ]


def build_talent_report(db: Session, talent: Talent, start: date, end: date) -> dict:
    """Assemble one talent's TALENT-FACING dataset (Fase 9.7, audience = talent).

    Only talent-appropriate figures — all money in the talent's 70% share. No
    pipeline, TA commission, funnel, prospectos/calificados, lost donut, or the
    payment-calendar placeholder (those are TA-internal and were removed).

    Data sources:
      - kpi_service.compute_talent_facing_kpis -> Row 1 (firmadas/cobrado/por cobrar, 70%)
      - kpi_service.account_status_breakdown -> Row 2 "Estado de tus cuentas" (70%)
      - won deals in period + Trello card    -> Row 3 detail table (70% + estado)
      - _talent_projection_70                -> page-2 projection (70%, forward-only)
    """
    talent_kpis = kpi_service.compute_talent_facing_kpis(db, talent.id, start, end)
    account_status = kpi_service.account_status_breakdown(db, talent.id)

    # Row 3 — campañas firmadas del mes, newest first, con su 70% y estado (badge).
    start_dt = datetime(start.year, start.month, start.day)
    end_excl = datetime(end.year, end.month, end.day) + timedelta(days=1)
    won_rows = (
        db.query(Deal)
        .filter(
            Deal.talent_id == talent.id,
            Deal.status == "won",
            Deal.won_time.isnot(None),
            Deal.won_time >= start_dt,
            Deal.won_time < end_excl,
        )
        .order_by(Deal.won_time.desc())
        .all()
    )
    signed = []
    for d in won_rows:
        card = db.query(TrelloCard).filter(TrelloCard.deal_id == d.id).first()
        cls, label = _signed_deal_estado(card, start, end)
        signed.append({
            "title": d.title,
            "date": _format_won_date(d.won_time.isoformat() if d.won_time else None),
            "value70": kpi_service._talent_70(d),
            "estado_cls": cls,
            "estado_label": label,
        })
    signed_total_70 = sum(s["value70"] for s in signed)

    projection70 = _talent_projection_70(db, talent)

    return {
        "talent_name": talent.name,
        "slug": filename_slug(talent.name),
        "talent_kpis": talent_kpis,               # Row 1 (70%)
        "account_status": account_status,         # Row 2 (70%)
        "signed_deals": signed,                   # Row 3 detail
        "signed_count": len(signed),
        "signed_total_70": signed_total_70,
        "projection70": projection70,             # page 2
        "projection70_svg": report_charts.talent_projection_svg(projection70),
    }


def build_report_context(
    db: Session,
    talents: list[Talent],
    period_value: str,
    start: date,
    end: date,
    now: datetime | None = None,
) -> dict:
    """Build the full document context (cover + one page per talent).

    Single talent -> cover shows that talent's name and headline KPIs.
    Multiple talents ('all') -> cover title is 'Reporte consolidado' and the
    headline KPIs are summed across talents (D2/D7).

    `now` overrides the generation timestamp — used by the golden-file test to
    render a deterministic cover (D10).
    """
    talent_reports = [build_talent_report(db, t, start, end) for t in talents]

    is_consolidated = len(talents) > 1
    title = "Reporte consolidado" if is_consolidated else (
        talents[0].name if talents else "Reporte"
    )

    now = now or datetime.utcnow()
    return {
        # Fase 9.7 (P1): the cover is branding-only — no sensitive KPIs (those are
        # 100%/all-time; the talent-facing 70% figures live on the talent pages).
        "title": title,
        "is_consolidated": is_consolidated,
        "talent_count": len(talents),
        "period_label": _period_label(period_value),
        "period_value": period_value,
        "talents": talent_reports,
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "generated_stamp": now.strftime("%Y-%m-%d %H:%M UTC"),
    }


def render_report_html(ctx: dict) -> str:
    """Render the full multi-page report HTML (cover + one page per talent)."""
    return _jinja_env.get_template("reports/base.html").render(ctx=ctx)
