import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.auth import router as auth_router
from app.config import settings
from app.routers import agent, audit, dashboard, data_health, health, leads, reports, sync, talents
from app.sync import scheduler as sync_scheduler

logger = logging.getLogger(__name__)

_REQUIRED_CREDENTIALS = [
    ("PIPEDRIVE_API_TOKEN", settings.PIPEDRIVE_API_TOKEN),
    ("PIPEDRIVE_DOMAIN", settings.PIPEDRIVE_DOMAIN),
    ("GOOGLE_SHEETS_ID", settings.GOOGLE_SHEETS_ID),
    ("GOOGLE_SERVICE_ACCOUNT_JSON", settings.GOOGLE_SERVICE_ACCOUNT_JSON),
    ("TRELLO_API_KEY", settings.TRELLO_API_KEY),
    ("TRELLO_TOKEN", settings.TRELLO_TOKEN),
    ("TRELLO_BOARD_IDS", settings.TRELLO_BOARD_IDS),
    ("ANTHROPIC_API_KEY", settings.ANTHROPIC_API_KEY),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = [name for name, val in _REQUIRED_CREDENTIALS if not val]
    if missing:
        logger.critical(
            "STARTUP WARNING: missing env vars %s — all integration calls will fail at runtime",
            ", ".join(missing),
        )
    sync_scheduler.start()
    yield
    sync_scheduler.shutdown()


app = FastAPI(title="SEG Talent Intelligence Dashboard", lifespan=lifespan)

app.include_router(auth_router.router)
app.include_router(talents.router)
app.include_router(health.router)
app.include_router(sync.router)
app.include_router(dashboard.router)
app.include_router(leads.router)
app.include_router(reports.router)
app.include_router(agent.router)
app.include_router(audit.router)
app.include_router(data_health.router)

# Static frontend mount MUST come last — registered after API routers so it
# does not shadow /auth/*, /talents, /health, /sync, /dashboard, /leads, /reports, /agent, or /api/audit.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
