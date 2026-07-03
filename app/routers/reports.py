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
  - Fase 9.5: /generate streams the PDF directly; /{id}/download regenerates the
    PDF on demand from the stored row (no PDF is persisted to disk).
"""
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Report, Talent
from app.schemas.reports import ReportGenerate, ReportHistoryItem
from app.services import periods as periods_service
from app.services import reports as reports_service


def _pdf_streaming_response(pdf_bytes: bytes, filename: str) -> StreamingResponse:
    """Stream PDF bytes as an attachment. `filename` is ASCII-safe (accent-stripped
    slug), so a plain Content-Disposition filename is sufficient."""
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

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


@router.post("/generate")
def generate_report(  # MUST be `def`, NOT `async def` — WeasyPrint is blocking I/O
    body: ReportGenerate,
    db: Session = Depends(get_db),
):
    """Generate a data-driven PDF report and stream it back (Fase 9.5).

    Target resolution (Fase 9.5 back-compat):
      - `talent_ids` (list of ids, or "all") takes precedence.
      - Otherwise the legacy singular `talent_id` is treated as [talent_id].
      - If neither is provided → 422.

    Period resolution (D8 back-compat):
      - period_type + period_value take precedence when both are present.
      - Otherwise the legacy `month` field is treated as period_type="month".
      - If neither is provided → 422.
      - period_value is validated via periods.parse_period → 400 on bad input (D6).

    Returns a StreamingResponse of the PDF (application/pdf, attachment). The
    report metadata row is upserted so it can be regenerated later from history.

    Errors:
      - 400 if period_value is malformed
      - 404 if a talent id is unknown
      - 422 if no target or no period is provided
    """
    # Resolve the target (Fase 9.5 back-compat): talent_ids wins over talent_id.
    if body.talent_ids is not None:
        talent_ids = body.talent_ids
    elif body.talent_id is not None:
        talent_ids = [body.talent_id]
    else:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either 'talent_ids' or 'talent_id'",
        )

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
        result = reports_service.generate_report_pdf(db, talent_ids, period_value, start, end)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return _pdf_streaming_response(result["pdf_bytes"], result["filename"])


@router.get("/", response_model=list[ReportHistoryItem])
def list_reports(db: Session = Depends(get_db)):
    """Return all generated reports newest-first with talent_name resolved.

    Auth-protected at router level (T-unauth-dl).
    """
    rows = reports_service.list_reports(db)
    return [ReportHistoryItem(**row) for row in rows]


@router.get("/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db)):
    """Re-render a stored report's PDF on demand and stream it (Fase 9.5).

    PDFs are no longer persisted to disk — the report is regenerated from the
    row's metadata (talent_ids + period). Auth-protected at router level.

    Errors:
      - 404 if the Report row does not exist
      - 404 if a talent referenced by the row no longer exists
    """
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    try:
        pdf_bytes, filename = reports_service.regenerate_report_pdf(db, report)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return _pdf_streaming_response(pdf_bytes, filename)
