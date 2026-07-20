"""Insights router — GET /api/insights/resumen (Módulo 1 / Resumen ejecutivo).

Router-level auth (all endpoints require a valid JWT). READ-ONLY: only reads
data and calls the NL agent; writes nothing to external services.

Declared `def` (NOT `async def`): the underlying agent uses the blocking
Anthropic SDK; FastAPI runs `def` endpoints in a threadpool.
"""
import threading
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.services import insights as insights_service

router = APIRouter(
    prefix="/api/insights",
    tags=["insights"],
    dependencies=[Depends(get_current_user)],  # all endpoints require auth
)

# In-memory rate limit for regenerate: max 1 per 60s per user.
_regen_lock = threading.Lock()
_regen_requests: dict[str, list[float]] = defaultdict(list)
_REGEN_LIMIT = 1
_REGEN_WINDOW = 60.0


def _check_regen_rate_limit(user_email: str) -> None:
    now = time.monotonic()
    with _regen_lock:
        recent = [t for t in _regen_requests[user_email] if now - t < _REGEN_WINDOW]
        if len(recent) >= _REGEN_LIMIT:
            _regen_requests[user_email] = recent
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Espera un momento antes de regenerar los insights.",
            )
        recent.append(now)
        _regen_requests[user_email] = recent


@router.get("/resumen")
def resumen(
    regenerate: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return executive insights for the Resumen (cached 1h). `regenerate=true`
    bypasses the cache (rate-limited 1/min/user). Never 5xx on agent failure —
    returns 200 with insights=[] and error so the Resumen keeps loading."""
    if regenerate:
        _check_regen_rate_limit(current_user.email)
    return insights_service.get_resumen_insights(db, regenerate=regenerate)
