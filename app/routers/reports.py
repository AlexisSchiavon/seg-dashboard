"""Reports router — authenticated endpoints for report generation and download.

All endpoints require a valid JWT cookie (router-level dependency).
Business logic lives in app/services/reports.py — this router only wires
HTTP concerns (request parsing, response serialization).

Security notes:
  - Router-level dependencies=[Depends(get_current_user)] protects ALL endpoints
    including /talents, /months, /generate, / (list), and /{id}/download
    (T-unauth-dl defense from STRIDE register).
  - generate_report endpoint is declared `def` (NOT `async def`) — WeasyPrint
    is blocking I/O; FastAPI runs it in a threadpool (RESEARCH.md Pitfall 3).
  - download_report: os.path.exists check returns 404 instead of leaking a
    500 stack trace when DB row points at a missing file (T-stale-path defense).
"""
import os
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Report, Talent
from app.schemas.reports import ReportGenerate, ReportHistoryItem, ReportOut
from app.services import periods as periods_service
from app.services import reports as reports_service

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_user)],  # router-level auth — protects ALL endpoints
)


@router.get("/talents", response_model=list[dict])
def get_report_talents(db: Session = Depends(get_db)):
    """Return active talents as [{id, name}] for the talent dropdown.

    Ordered by name ascending so the dropdown is alphabetically sorted.
    """
    talents = (
        db.query(Talent.id, Talent.name)
        .filter(Talent.active.is_(True))
        .order_by(Talent.name)
        .all()
    )
    return [{"id": row[0], "name": row[1]} for row in talents]


@router.get("/months", response_model=list[str])
def get_available_months(talent_id: int | None = None, db: Session = Depends(get_db)):
    """Return distinct YYYY-MM strings for months that have a won deal (Fase 7).

    Won-based (Deal.won_time) and global — the period filter operates on won_time,
    so the dropdown must offer only months that actually have signings (offering
    empty months would be confusing). `talent_id` is accepted but ignored, kept
    for back-compat with the pre-Fase-7 query string.
    """
    return periods_service.available_months(db)


@router.get("/quarters", response_model=list[str])
def get_available_quarters(db: Session = Depends(get_db)):
    """Return distinct YYYY-QN strings for quarters that have a won deal (Fase 7).

    Sourced from Deal.won_time (won deals only) — the dropdown counterpart to
    /months for quarter selection. Descending (most recent first).
    """
    return periods_service.available_quarters(db)


@router.post("/generate", response_model=ReportOut)
def generate_report(  # MUST be `def`, NOT `async def` — WeasyPrint is blocking I/O
    body: ReportGenerate,
    db: Session = Depends(get_db),
):
    """Generate a data-driven PDF report for a talent + period (month or quarter).

    Fase 9 (D8): the report is 100% Python-computed — no Claude narrative.

    Period resolution (D8 back-compat):
      - period_type + period_value take precedence when both are present.
      - Otherwise the legacy `month` field is treated as period_type="month".
      - If neither is provided → 422.
      - period_value is validated via periods.parse_period → 400 on bad input (D6).

    Errors:
      - 400 if period_value is malformed
      - 404 if talent not found (ValueError from service)
      - 422 if neither month nor period_type/period_value provided
    """
    # Resolve the period (D8 back-compat): period_type/period_value win over month.
    if body.period_type is not None and body.period_value is not None:
        period_type, period_value = body.period_type, body.period_value
    elif body.month is not None:
        period_type, period_value = "month", body.month
    else:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either 'month' or both 'period_type' and 'period_value'",
        )

    # Validate + parse the period (D6) — malformed input → 400.
    try:
        start, end = periods_service.parse_period(period_type, period_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        result = reports_service.generate_report(db, body.talent_id, period_value, start, end)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Talent not found",
        ) from exc

    return ReportOut(
        id=result["id"],
        talent_id=result["talent_id"],
        talent_name=result["talent_name"],
        month=result["month"],
        generated_at=result["generated_at"],
        file_path=result["file_path"],
        file_size_bytes=result["file_size_bytes"],
    )


@router.get("/", response_model=list[ReportHistoryItem])
def list_reports(db: Session = Depends(get_db)):
    """Return all generated reports newest-first with talent_name resolved.

    Auth-protected at router level (T-unauth-dl).
    """
    rows = reports_service.list_reports(db)
    return [ReportHistoryItem(**row) for row in rows]


@router.get("/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db)):
    """Stream the PDF file for a given report as an attachment download.

    Auth-protected at router level (T-unauth-dl).

    Errors:
      - 404 if Report row not found in DB
      - 404 if Report row exists but PDF file is missing on disk (T-stale-path defense)
    """
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    if not os.path.exists(report.file_path):
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="PDF file not found on disk",
        )

    talent = db.get(Talent, report.talent_id)
    talent_name = talent.name if talent is not None else "Sin-talento"
    # Replace spaces with hyphens for a clean filename
    safe_name = talent_name.replace(" ", "-")

    # CR-02: RFC 5987 / RFC 6266 compliant Content-Disposition.
    # filename= is an ASCII fallback (month only) for old clients.
    # filename*= uses UTF-8 percent-encoding for non-ASCII talent names
    # (e.g. "María-López-2026-05.pdf") so Safari/Firefox preserve the full name.
    filename_ascii = f"reporte-{report.month}.pdf"
    filename_utf8 = f"reporte-{safe_name}-{report.month}.pdf"
    encoded = quote(filename_utf8, safe="-.")

    return FileResponse(
        path=report.file_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename_ascii}"; '
                f"filename*=UTF-8''{encoded}"
            )
        },
    )
