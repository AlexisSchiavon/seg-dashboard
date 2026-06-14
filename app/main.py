from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.auth import router as auth_router
from app.routers import dashboard, health, sync, talents
from app.sync import scheduler as sync_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_scheduler.start()
    yield
    sync_scheduler.shutdown()


app = FastAPI(title="SEG Talent Intelligence Dashboard", lifespan=lifespan)

app.include_router(auth_router.router)
app.include_router(talents.router)
app.include_router(health.router)
app.include_router(sync.router)
app.include_router(dashboard.router)

# Static frontend mount MUST come last — registered after API routers so it
# does not shadow /auth/*, /talents, /health, /sync, or /dashboard.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
