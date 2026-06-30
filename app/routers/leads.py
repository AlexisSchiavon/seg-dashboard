"""Leads router — authenticated endpoints for lead counts and listing.

All endpoints require a valid JWT cookie (router-level dependency, T-03-03).
Business logic lives in app/services/leads.py — this router only wires
HTTP concerns (request parsing, response serialization).
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Talent
from app.schemas.leads import LeadDetail, LeadRow, LeadsSummary, TalentLeadBar
from app.services import leads as leads_service

router = APIRouter(
    prefix="/leads",
    tags=["leads"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[LeadRow])
def list_leads(
    talent_id: int | None = None,
    status: str | None = None,
    fuente: str | None = None,
    db: Session = Depends(get_db),
):
    """Return a filterable list of leads with talent_name + status_display resolved.

    Filters:
    - talent_id: restrict to a specific talent (404 if not found)
    - status: filter by raw status_filtrado value
    - fuente: filter by source (e.g. "Gmail")

    T-03B-02: auth-protected via router-level Depends(get_current_user).
    T-03B-03: talent_id coerced to int by FastAPI (422 on non-int);
              nonexistent talent_id → 404; status/fuente used only as
              parameterized SQLAlchemy filter values.
    """
    if talent_id is not None:
        talent = db.get(Talent, talent_id)
        if talent is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Talent not found",
            )

    rows = leads_service.leads_list(db, talent_id=talent_id, status=status, fuente=fuente)
    return [LeadRow(**row) for row in rows]


@router.get("/summary", response_model=LeadsSummary)
def get_leads_summary(db: Session = Depends(get_db)):
    """Return total lead count, calificados count, and per-talent breakdown."""
    summary = leads_service.leads_summary(db)
    bars = leads_service.leads_by_talent(db)
    return LeadsSummary(
        leads_totales=summary["leads_totales"],
        calificados=summary["calificados"],
        por_talento=[TalentLeadBar(**bar) for bar in bars],
    )


# NOTE: declared AFTER /summary so the literal "/leads/summary" route matches
# first — otherwise "summary" would be coerced against {lead_id: int} (422).
@router.get("/{lead_id}", response_model=LeadDetail)
def get_lead_detail(lead_id: int, db: Session = Depends(get_db)):
    """Return the full detail for one lead (8.2) — drives the detail modal.

    Auth inherited from the router-level Depends(get_current_user) (no new auth).
    404 when the lead does not exist. NULL Sheet fields are returned as null;
    the frontend renders the D7 fallback copy.
    """
    detail = leads_service.lead_detail(db, lead_id)
    if detail is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    return LeadDetail(**detail)
