from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth.security import verify_password, create_access_token
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.auth import UserRead
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_TOKEN_EXPIRE = timedelta(days=7)  # D-02


@router.post("/login")
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        # D-06: generic message, do not reveal whether the email exists
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": user.email}, ACCESS_TOKEN_EXPIRE)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,  # env-configurable, Pitfall 4 / T-01-03 — never hardcoded
        samesite="lax",
        max_age=int(ACCESS_TOKEN_EXPIRE.total_seconds()),
        path="/",
    )
    return {"status": "ok"}


@router.post("/logout")
def logout(response: Response, current_user: User = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")  # D-05
    return {"status": "ok"}


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user
