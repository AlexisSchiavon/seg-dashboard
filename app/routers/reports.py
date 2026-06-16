"""Reports router — authenticated endpoints for report generation and download.

All endpoints require a valid JWT cookie (router-level dependency).
Business logic lives in app/services/reports.py — this router only wires
HTTP concerns (request parsing, response serialization).

Security notes:
  - Router-level dependencies=[Depends(get_current_user)] protects ALL endpoints
    including /talents, /months, and /generate (T-unauth-dl defense).
  - generate_report endpoint is declared `def` (NOT `async def`) — WeasyPrint
    is blocking I/O; FastAPI runs it in a threadpool (RESEARCH.md Pitfall 3).
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Talent
from app.schemas.reports import ReportGenerate, ReportHistoryItem, ReportOut
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
def get_available_months(talent_id: int, db: Session = Depends(get_db)):
    """Return distinct YYYY-MM strings from Deal.add_time for the given talent.

    Returns [] if the talent has no deals or if talent_id does not exist.
    """
    return reports_service.available_months(db, talent_id)


@router.post("/generate", response_model=ReportOut)
def generate_report(  # MUST be `def`, NOT `async def` — WeasyPrint is blocking I/O
    body: ReportGenerate,
    db: Session = Depends(get_db),
):
    """Generate an AI-narrated PDF report for a talent + month.

    Orchestration:
      1. Validate talent exists (404 if not)
      2. Build Python-computed payload (kpis/funnel/leads)
      3. Call Claude for 3 narrative prose sections
      4. Render HTML → PDF via WeasyPrint (blocking — runs in threadpool)
      5. Upsert Report row in DB
      6. Return ReportOut with narrative sections for in-page preview

    Errors:
      - 404 if talent not found (ValueError from service)
      - 502 if Claude returns non-JSON (ValueError with specific message)
    """
    try:
        result = reports_service.generate_report(db, body.talent_id, body.month)
    except ValueError as exc:
        msg = str(exc)
        if "non-JSON" in msg or "Claude returned" in msg:
            raise HTTPException(
                status_code=http_status.HTTP_502_BAD_GATEWAY,
                detail="Error al generar narrativa",
            ) from exc
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
        narrative=result["narrative"],
    )
