"""Leads router — authenticated endpoints for lead counts and listing.

All endpoints require a valid JWT cookie (router-level dependency, T-03-03).
Business logic lives in app/services/leads.py — this router only wires
HTTP concerns (request parsing, response serialization).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.schemas.leads import LeadsSummary, TalentLeadBar
from app.services import leads as leads_service

router = APIRouter(
    prefix="/leads",
    tags=["leads"],
    dependencies=[Depends(get_current_user)],
)


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
