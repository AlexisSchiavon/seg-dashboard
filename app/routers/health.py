from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    # AUTH-03 / T-03-01: public liveness probe — no auth dependency, no
    # internal detail leaked. Always returns HTTP 200; DB status is carried
    # in the body so load balancers checking for 2xx don't flap (Open
    # Question 2).
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    return {"status": "ok", "database": db_status}
