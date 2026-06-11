from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.auth import router as auth_router
from app.routers import talents

app = FastAPI(title="SEG Talent Intelligence Dashboard")

app.include_router(auth_router.router)
app.include_router(talents.router)

# Static frontend mount MUST come last — registered after API routers so it
# does not shadow /auth/* (and Plan 02/03 routers added above this line).
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
