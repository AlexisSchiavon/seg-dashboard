# Phase 2: Pipedrive Integration & Core Dashboard - Pattern Map

**Mapped:** 2026-06-12
**Files analyzed:** 17
**Analogs found:** 17 / 17 (all role-match or partial-match; this is the first integration/sync/dashboard phase, so no exact prior analogs exist for `integrations/`, `sync/`, `services/` modules — closest Phase 1 conventions are mapped instead)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `app/models.py` (add `Deal`, `DealStageEvent`, `SyncLog`) | model | CRUD | `app/models.py` (existing `Talent`/`TalentProduct`) | exact (same file, additive) |
| `alembic/versions/xxxx_add_deals_dealstageevents_synclogs.py` | migration | batch | `alembic/versions/324116cbf0dd_initial_schema_users_talents_talent_.py` | exact |
| `app/integrations/base.py` | utility | request-response | `app/auth/security.py` (thin stateless helper module) | partial-match |
| `app/integrations/pipedrive.py` | service (HTTP client wrapper) | request-response + batch | `app/auth/security.py` (module-level config-driven helper) + RESEARCH.md Pattern 1/2 | partial-match (no prior httpx integration exists; RESEARCH.md provides the canonical shape) |
| `app/sync/__init__.py` | config | — | `app/services/__init__.py` (empty placeholder package) | exact |
| `app/sync/scheduler.py` | service (background scheduler) | event-driven | `app/main.py` (startup wiring) + RESEARCH.md Pattern "APScheduler lifespan integration" | partial-match |
| `app/sync/jobs.py` | service (sync orchestration) | batch + CRUD | `app/scripts/seed_talents.py` (SessionLocal-scoped batch write) | role-match |
| `app/services/kpis.py` | service (aggregation/read) | CRUD (read aggregates) | `app/routers/talents.py` (query patterns over `Session`) | role-match |
| `app/services/funnel.py` | service (aggregation/read) | CRUD (read aggregates) | `app/routers/talents.py` (query patterns over `Session`) | role-match |
| `app/routers/dashboard.py` | router/controller | request-response | `app/routers/talents.py` | exact |
| `app/routers/sync.py` (or merged into `dashboard.py`) | router/controller | request-response (async trigger) | `app/routers/talents.py` (auth + router wiring) | role-match |
| `app/schemas/dashboard.py` | schema (Pydantic models) | transform | `app/schemas/talent.py` | exact |
| `app/scripts/match_talent_products.py` | script (one-time batch) | batch | `app/scripts/seed_talents.py` | exact |
| `app/main.py` (add dashboard/sync routers + lifespan scheduler) | config/bootstrap | event-driven | `app/main.py` (current file) | exact (same file, additive) |
| `frontend/index.html` (or dashboard shell) | component (HTML shell) | request-response (fetch JSON) | `frontend/login.html` + `.planning/reference/mockup.html` | role-match (mockup is the structural template) |
| `frontend/js/dashboard.js` (new) | component (frontend logic) | request-response (fetch + render) | `frontend/js/auth.js` (`apiFetch` pattern) | role-match |
| `frontend/css/styles.css` (extend) | config (design tokens/components) | transform (CSS) | `frontend/css/styles.css` (existing) + `.planning/reference/mockup.html` `<style>` block | exact |
| `tests/test_pipedrive_integration.py`, `tests/test_sync.py`, `tests/test_kpis.py`, `tests/test_funnel.py`, `tests/test_dashboard.py` | test | request-response / unit | `tests/test_talents.py` + `tests/conftest.py` | exact |

---

## Pattern Assignments

### `app/models.py` (model, CRUD) — add `Deal`, `DealStageEvent`, `SyncLog`

**Analog:** `app/models.py` (current file, lines 1-40 — same file, additive)

**Imports pattern** (lines 1-6):
```python
from datetime import datetime

from sqlalchemy import String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
```
Add `Float`, `Integer` to the `sqlalchemy` import for the new tables.

**Core declarative pattern** (lines 18-39, `Talent`/`TalentProduct`):
```python
class Talent(Base):
    __tablename__ = "talents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)  # D-13
    active: Mapped[bool] = mapped_column(Boolean, default=True)  # D-13
    category: Mapped[str | None] = mapped_column(String, nullable=True)  # D-13 (niche)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)

    products: Mapped[list["TalentProduct"]] = relationship(
        back_populates="talent", cascade="all, delete-orphan"
    )


class TalentProduct(Base):
    __tablename__ = "talent_products"  # D-14

    id: Mapped[int] = mapped_column(primary_key=True)
    talent_id: Mapped[int] = mapped_column(ForeignKey("talents.id"), index=True)
    pipedrive_product_id: Mapped[int | None] = mapped_column(nullable=True)  # D-15: null in Phase 1

    talent: Mapped["Talent"] = relationship(back_populates="products")
```

**Apply this convention to the new tables:**
- `id: Mapped[int] = mapped_column(primary_key=True)` first field, always.
- `Mapped[X | None]` + `nullable=True` for optional columns (matches RESEARCH.md Pattern 3 schema for `Deal.talent_id`, `loss_reason`, `brand_category`, `expected_collection_date`, `DealStageEvent.from_stage`/`from_status`).
- `index=True` on FK/lookup columns that will be queried frequently (`Deal.pipedrive_id` unique+index per RESEARCH.md, `DealStageEvent.deal_pipedrive_id` index).
- `server_default=func.now()` for `created_at`/`detected_at` timestamps, matching `User.created_at` (line 15: `mapped_column(DateTime, server_default=func.now())`).
- `relationship(back_populates=..., cascade=...)` only where Phase 1 already establishes a parent/child (Talent <-> TalentProduct); `Deal.talent_id` is a plain nullable FK — no cascade needed (D-17 requires `Deal` rows to survive even if `talent_id IS NULL`).

---

### `alembic/versions/xxxx_add_deals_dealstageevents_synclogs.py` (migration, batch)

**Analog:** `alembic/versions/324116cbf0dd_initial_schema_users_talents_talent_.py` (full file, 61 lines)

**Header pattern** (lines 1-18):
```python
"""initial schema: users, talents, talent_products

Revision ID: 324116cbf0dd
Revises:
Create Date: 2026-06-11 12:44:07.883247

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '324116cbf0dd'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```
For the new migration: generate via `uv run alembic revision --autogenerate -m "add deals, deal_stage_events, sync_logs"` after adding the models — `down_revision` must point to `324116cbf0dd` (the current head).

**`upgrade()` / `op.create_table` + index pattern** (lines 21-49):
```python
def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('talents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('category', sa.String(), nullable=True),
    sa.Column('photo_url', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_talents_name'), 'talents', ['name'], unique=True)
    ...
    op.create_table('talent_products',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('talent_id', sa.Integer(), nullable=False),
    sa.Column('pipedrive_product_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['talent_id'], ['talents.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_talent_products_talent_id'), 'talent_products', ['talent_id'], unique=False)
    # ### end Alembic commands ###
```

**`downgrade()` pattern** (lines 52-61) — reverse order, drop indexes before tables:
```python
def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_talent_products_talent_id'), table_name='talent_products')
    op.drop_table('talent_products')
    ...
    # ### end Alembic commands ###
```

**Apply to new migration:** `create_table('deals', ...)` with `sa.UniqueConstraint`/`op.create_index(..., unique=True)` for `pipedrive_id`, FK to `talents.id` for `talent_id` (nullable), then `create_table('deal_stage_events', ...)` with index on `deal_pipedrive_id`, then `create_table('sync_logs', ...)`. `downgrade()` drops in reverse dependency order (sync_logs, deal_stage_events, deals).

---

### `app/integrations/base.py` + `app/integrations/pipedrive.py` (service, request-response + batch)

**No direct codebase analog** — Phase 1 has no `httpx` integration code (`app/integrations/__init__.py` is an empty placeholder package). Use RESEARCH.md Pattern 1/2 verbatim (already vetted against v2 API docs), but follow the project's **config access convention** from `app/auth/security.py` / `app/config.py`.

**Config access convention** (from `app/config.py`, lines 1-25 — already read by `app/auth/security.py` and `app/database.py`):
```python
from app.config import settings
```
`settings.PIPEDRIVE_API_TOKEN` and `settings.PIPEDRIVE_DOMAIN` are already defined as empty-string defaults (`app/config.py` lines 14-15) — no config changes needed, just consume them.

**Core HTTP client pattern** (RESEARCH.md Pattern 1, CITED against Pipedrive v2 docs):
```python
# app/integrations/base.py / pipedrive.py
import httpx
from app.config import settings

BASE_URL = f"https://{settings.PIPEDRIVE_DOMAIN}.pipedrive.com/api/v2"

def _client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"x-api-token": settings.PIPEDRIVE_API_TOKEN},  # v2: header, NOT ?api_token=
        timeout=30.0,
    )

def _paginate(client: httpx.Client, path: str, params: dict | None = None):
    params = dict(params or {})
    params.setdefault("limit", 500)
    cursor = None
    while True:
        if cursor:
            params["cursor"] = cursor
        resp = _get_with_retry(client, path, params)
        payload = resp.json()
        yield from (payload.get("data") or [])
        cursor = (payload.get("additional_data") or {}).get("next_cursor")
        if not cursor:
            break

def _get_with_retry(client: httpx.Client, path: str, params: dict, max_attempts: int = 5):
    import time
    for attempt in range(max_attempts):
        resp = client.get(path, params=params)
        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After", 2 ** attempt))
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp
```

**Field/option resolution pattern** (RESEARCH.md Pattern 2 — required for PIPE-04, Pitfall 2):
```python
def build_field_maps(client: httpx.Client) -> tuple[dict[str, str], dict[str, dict[int, str]]]:
    fields = list(_paginate(client, "/dealFields"))
    key_by_name = {f["name"]: f["key"] for f in fields}
    option_labels: dict[str, dict[int, str]] = {}
    for f in fields:
        if f.get("options"):
            option_labels[f["key"]] = {opt["id"]: opt["label"] for opt in f["options"]}
    return key_by_name, option_labels

def resolve_custom_field(deal: dict, field_key: str, option_labels: dict[str, dict[int, str]]):
    cf = (deal.get("custom_fields") or {}).get(field_key)
    if cf is None:
        return None
    raw = cf.get("value")
    if field_key in option_labels and raw is not None:
        return option_labels[field_key].get(raw)
    return raw
```

**Bulk deal-products pattern** (RESEARCH.md, CITED against Pipedrive changelog):
```python
def get_deal_products_bulk(client: httpx.Client, deal_ids: list[int]) -> dict[int, list[dict]]:
    """GET /api/v2/deals/products?deal_ids=1,2,3 — up to 100 deal IDs per call."""
    result: dict[int, list[dict]] = {}
    for chunk_start in range(0, len(deal_ids), 100):
        chunk = deal_ids[chunk_start:chunk_start + 100]
        for item in _paginate(client, "/deals/products", {"deal_ids": ",".join(map(str, chunk))}):
            result.setdefault(item["deal_id"], []).append(item)
    return result
```

**Error handling:** No try/except wrapping at the integration layer — let `httpx.HTTPStatusError`/`httpx.RequestError` propagate to `app/sync/jobs.py`, which catches them and writes `SyncLog.status = "error"` / `SyncLog.error_message = str(exc)` (see `app/sync/jobs.py` section below). This matches the project's "fail fast at the boundary, handle at the orchestration layer" approach (no integration-layer error handling exists in Phase 1 to deviate from).

---

### `app/sync/scheduler.py` (service, event-driven)

**No direct codebase analog** — `app/main.py` currently has no `lifespan` context manager. RESEARCH.md provides the canonical FastAPI lifespan + APScheduler wiring; apply the project's existing **app construction style** from `app/main.py`.

**Current `app/main.py` (full file, 16 lines) — app construction style to extend:**
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.auth import router as auth_router
from app.routers import health, talents

app = FastAPI(title="SEG Talent Intelligence Dashboard")

app.include_router(auth_router.router)
app.include_router(talents.router)
app.include_router(health.router)

# Static frontend mount MUST come last — registered after API routers so it
# does not shadow /auth/*, /talents, or /health.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
```

**Scheduler module pattern** (RESEARCH.md "APScheduler lifespan integration"):
```python
# app/sync/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import SessionLocal
from app.sync.jobs import sync_pipedrive

scheduler = BackgroundScheduler()

def _run_pipedrive_sync():
    db = SessionLocal()
    try:
        sync_pipedrive(db)
    finally:
        db.close()

def start():
    scheduler.add_job(_run_pipedrive_sync, "interval", hours=1, id="sync_pipedrive", replace_existing=True)
    scheduler.start()

def shutdown():
    scheduler.shutdown(wait=False)
```

**`app/main.py` additions** — add `lifespan` while preserving the existing router/static-mount order (static mount MUST remain last per the existing comment, lines 13-15):
```python
from contextlib import asynccontextmanager
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
app.include_router(dashboard.router)   # NEW
app.include_router(sync.router)         # NEW (or merge into dashboard.router)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
```

**Concurrency guard (Pitfall 5)** — no existing lock pattern in the codebase; implement as a check against the latest `SyncLog.status == "running"` row (with a staleness timeout) inside `app/sync/jobs.py`'s entry point, called from both `scheduler.py`'s job and the manual `POST /sync/pipedrive` endpoint.

---

### `app/sync/jobs.py` (service, batch + CRUD)

**Closest analog:** `app/scripts/seed_talents.py` (full file, 43 lines) — `SessionLocal`-scoped batch upsert with idempotency check.

**Session-scoped batch pattern** (lines 1-38):
```python
from app.database import SessionLocal
from app.models import Talent

TALENT_NAMES = [
    "Navarretes Show",
    ...
]


def seed_talents(session_factory=SessionLocal):
    db = session_factory()
    try:
        existing = {t.name for t in db.query(Talent).all()}
        for name in TALENT_NAMES:
            if name not in existing:
                db.add(Talent(name=name, active=True))  # D-15: products left null
        db.commit()
    finally:
        db.close()
```

**Apply to `sync_pipedrive(db: Session) -> SyncLog`:**
- Accept `db: Session` as a parameter (NOT construct its own `SessionLocal()`), so it can be called from both `app/sync/scheduler.py` (which creates the session) and a test fixture (`db_session` from `tests/conftest.py`) and the manual sync endpoint.
- Same `existing = {row.pipedrive_id: row for row in db.query(Deal).all()}` lookup-then-upsert idempotency style as `seed_talents`'s `existing = {t.name for t in ...}`.
- `db.commit()` once at the end (or per-batch if deal volume grows) — matches `seed_talents`'s single commit, `db.add(...)` loop pattern.
- Write `SyncLog` row: `started_at` at entry, `status="running"` written/committed immediately (so the concurrency guard can read it from a concurrent request), then update to `status="success"`/`"error"` + `finished_at` + `records_synced` at the end — this is new to the codebase (no prior multi-phase-commit pattern), follow RESEARCH.md's `SyncLog` schema (Pattern 3) exactly.
- Pitfall 3 (first-sync no spurious `DealStageEvent`): `if existing_deal is not None and (existing_deal.stage_id != incoming_stage_id or existing_deal.status != incoming_status): db.add(DealStageEvent(...))` — only on UPDATE, never on INSERT.
- Pitfall 4 (Sin talento asignado in global totals): write `Deal.talent_id = None` (not a sentinel talent row) when `talent_products.pipedrive_product_id` has no match — `app/services/kpis.py` queries handle the `NULL` bucket explicitly (see below).

---

### `app/services/kpis.py` + `app/services/funnel.py` (service, CRUD read-aggregates)

**Closest analog:** `app/routers/talents.py` (lines 1-25) for `Session`-based query style — but these are new service-layer modules (no router coupling), so extract the **query patterns** only, not the router/HTTPException wrapping.

**Query style to follow** (from `app/routers/talents.py`, lines 22-24 and 50-56):
```python
@router.get("", response_model=list[TalentRead])
def list_talents(db: Session = Depends(get_db)):
    return db.query(Talent).all()
```
```python
@router.get("/{talent_id}/products", response_model=list[TalentProductRead])
def list_talent_products(talent_id: int, db: Session = Depends(get_db)):
    talent = db.get(Talent, talent_id)
    if talent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talent not found")
    return talent.products
```

**Apply to `services/kpis.py`:**
- Functions take `db: Session` as the first parameter (plain functions, not `Depends`-wired — `Depends` belongs in `routers/dashboard.py`, which calls these functions).
- `db.query(Deal).filter(...)` / `db.query(func.sum(Deal.value)).filter(...)` for aggregates — use SQLAlchemy 2.0 `func` (already imported in `app/models.py` line 3 as `from sqlalchemy import ... func`).
- **Pitfall 4 — global vs per-talent split:**
  - Global KPIs: `db.query(Deal)` directly, NO JOIN to `Talent` (so `talent_id IS NULL` rows are included).
  - Per-talent KPIs: `db.query(Deal).filter(Deal.talent_id == talent_id)`.
  - Ranking: `db.query(Talent.id, Talent.name, func.sum(Deal.value)).outerjoin(Deal, Deal.talent_id == Talent.id).group_by(Talent.id)` PLUS a separate query for `db.query(func.count(Deal.id), func.sum(Deal.value)).filter(Deal.talent_id.is_(None))` to build the "Sin talento asignado" row (D-17, UI-SPEC copy: `"Sin talento asignado"`).
- Commission/Sin-cotizar are READ directly from `Deal.commission_amount` / `Deal.is_sin_cotizar` (computed at sync-write time per RESEARCH.md "Don't Hand-Roll" — no recomputation here).

**Apply to `services/funnel.py`:**
- 6-stage aggregation: `db.query(Deal.stage_name, func.count(Deal.id), func.sum(Deal.value)).filter(Deal.status == "open").group_by(Deal.stage_name)`.
- Bottleneck detection (DASH-03, RESEARCH.md Pattern 4): snapshot-ratio computation over the ordered stage list, with the minimum-sample-size fallback returning the UI-SPEC's exact copy `"Datos insuficientes para detectar cuellos de botella"`.
- Activity feed (DASH-01): `db.query(DealStageEvent).order_by(DealStageEvent.detected_at.desc()).limit(N)`.

---

### `app/routers/dashboard.py` (controller, request-response)

**Analog:** `app/routers/talents.py` (full file, 89 lines)

**Imports pattern** (lines 1-13):
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Talent, TalentProduct
from app.schemas.talent import (
    TalentCreate,
    TalentProductCreate,
    TalentProductRead,
    TalentRead,
    TalentUpdate,
)
```
For `dashboard.py`: import `app.services.kpis`, `app.services.funnel`, and the new `app/schemas/dashboard.py` response models.

**Router declaration + auth pattern** (lines 15-19) — this is the **shared auth pattern** (see Shared Patterns below):
```python
router = APIRouter(
    prefix="/talents",
    tags=["talents"],
    dependencies=[Depends(get_current_user)],
)
```
For `dashboard.py`: `router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])`.

**Read-endpoint pattern** (lines 22-24):
```python
@router.get("", response_model=list[TalentRead])
def list_talents(db: Session = Depends(get_db)):
    return db.query(Talent).all()
```
Apply directly to `GET /dashboard/summary`, `GET /dashboard/talents/{id}`, `GET /dashboard/funnel`, `GET /dashboard/sync-status` — each delegates to a `services/kpis.py`/`services/funnel.py` function and returns a Pydantic response model (`response_model=DashboardSummary`, etc.).

**404 pattern** (lines 36-47, `update_talent`) — apply to `GET /dashboard/talents/{id}` for an unknown talent id:
```python
@router.patch("/{talent_id}", response_model=TalentRead)
def update_talent(talent_id: int, payload: TalentUpdate, db: Session = Depends(get_db)):
    talent = db.get(Talent, talent_id)
    if talent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talent not found")
    ...
```

---

### `app/routers/sync.py` (controller, request-response — async trigger, D-22/D-23)

**Analog:** `app/routers/talents.py` for router/auth wiring (same as above); **no existing async-trigger endpoint** in the codebase — D-22/D-23 introduce a new pattern (FastAPI `BackgroundTasks` per RESEARCH.md's "Alternatives Considered" table).

```python
from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db, SessionLocal
from app.sync.jobs import sync_pipedrive

router = APIRouter(prefix="/sync", tags=["sync"], dependencies=[Depends(get_current_user)])


@router.post("/pipedrive", status_code=status.HTTP_202_ACCEPTED)
def trigger_sync(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Pitfall 5: check SyncLog.status == "running" before scheduling — no-op if already in flight
    ...
    background_tasks.add_task(_run_sync_in_background)
    return {"status": "accepted"}


def _run_sync_in_background():
    db = SessionLocal()
    try:
        sync_pipedrive(db)
    finally:
        db.close()
```
**Error handling:** Mirrors `app/sync/scheduler.py`'s `_run_pipedrive_sync` (own `SessionLocal`, `finally: db.close()`) — exceptions inside `sync_pipedrive` are caught internally and written to `SyncLog`, not re-raised to the background task runner.

---

### `app/schemas/dashboard.py` (schema, transform)

**Analog:** `app/schemas/talent.py` (full file, 38 lines)

**Pydantic v2 model conventions** (lines 1-37):
```python
from pydantic import BaseModel


class TalentProductRead(BaseModel):
    id: int
    pipedrive_product_id: int | None = None

    model_config = {"from_attributes": True}


class TalentRead(TalentBase):
    id: int
    products: list[TalentProductRead] = []

    model_config = {"from_attributes": True}
```

**Apply to `schemas/dashboard.py`:**
- `model_config = {"from_attributes": True}` on any response model backed directly by an ORM row (e.g., a `DealRead`/`SyncStatusRead` mapped from `Deal`/`SyncLog`).
- Plain `BaseModel` (no `from_attributes`) for aggregate/computed response shapes that services build as dicts (e.g., `DashboardSummary`, `FunnelOverview`, `TalentDetail`, `BrandCategoryBreakdown`, `LostOpportunitySummary`) — these are constructed by `services/kpis.py`/`services/funnel.py`, not read directly from a single ORM object.
- `field: type | None = None` optional-field style (line 6, 12, 18-19) for any nullable response fields (e.g., `bottleneck: BottleneckInfo | None = None` when sample size is insufficient).

---

### `app/scripts/match_talent_products.py` (script, batch)

**Analog:** `app/scripts/seed_talents.py` (full file, 43 lines) AND `app/scripts/seed_admin.py` (full file, 24 lines) — both establish the "module-level function + `if __name__ == '__main__':`" one-time script convention.

**`seed_talents.py` idempotent batch pattern** (lines 29-43):
```python
def seed_talents(session_factory=SessionLocal):
    db = session_factory()
    try:
        existing = {t.name for t in db.query(Talent).all()}
        for name in TALENT_NAMES:
            if name not in existing:
                db.add(Talent(name=name, active=True))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_talents()
```

**`seed_admin.py` idempotent upsert pattern** (lines 7-23) — closer to what `match_talent_products.py` needs (update-or-create on `TalentProduct`):
```python
def seed_admin():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        hashed = get_password_hash(settings.ADMIN_PASSWORD)
        if user:
            user.hashed_password = hashed  # idempotent rotation
        else:
            user = User(email=settings.ADMIN_EMAIL, hashed_password=hashed)
            db.add(user)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
```

**Apply to `match_talent_products.py`:** combine both — `session_factory=SessionLocal` parameter (for test injection, per `seed_talents`) + upsert-or-create on `TalentProduct` (per `seed_admin`'s `if tp: ... else: ...` pattern). Use RESEARCH.md's full skeleton (rapidfuzz `process.extractOne` + `THRESHOLD = 85` + D-18 unmapped-products report printed to stdout) — this is the only file in Phase 2 where RESEARCH.md's code example is the primary source (no closer analog exists for fuzzy-matching).

---

### `frontend/index.html` (component, request-response/fetch)

**Analog:** `.planning/reference/mockup.html` (structural template, 37.5KB) for markup; `frontend/login.html` for the project's actual HTML file conventions (head/link/script wiring).

**Nav + tabbar shell** (mockup body, verbatim — repurpose `.live-pill` per D-21):
```html
<nav class="nav">
  <div class="nav-logo">SEG <span>·</span> Intelligence</div>
  <div class="nav-right">
    <div class="live-pill"><span class="live-dot"></span>Última sync: hace -- min</div>
    <select class="sel" id="gMes">
      <option>Mayo 2025</option>
    </select>
  </div>
</nav>
<div class="tabbar">
  <div class="tab active" onclick="setPage('overview')">Resumen</div>
  <div class="tab" onclick="setPage('talent')">Por talento</div>
  <div class="tab" onclick="setPage('funnel')">Funnel</div>
</div>
```

**KPI grid markup** (mockup, Resumen page):
```html
<div class="section">
  <div class="section-title">Resumen ejecutivo · Mayo 2025</div>
  <div class="kpi-grid">
    <div class="kpi accent">
      <div class="kpi-label">Pipeline total</div>
      <div class="kpi-val accent">$453K</div>
      <div class="kpi-sub">MXN este mes</div>
    </div>
    <!-- repeat per KPI: amber/green/purple variants -->
  </div>
</div>
```
Per UI-SPEC: drop "Leads totales"/"Calificados" tiles (no Phase 2 data source), keep "Pipeline total" (accent), "En negociación" (amber), "Cerrados" (purple), "En campaña" (green).

**Ranking row markup** (mockup):
```html
<div class="card" style="padding:14px 16px;">
  <div class="rank-row">
    <div class="rank-num gold">1</div>
    <div class="rank-avatar" style="background:rgba(107,84,214,0.2);color:#a594f0;">EM</div>
    <div class="rank-info">
      <div class="rank-name">Emicanico</div>
      <div class="rank-nicho">Gaming · 5.1M seg.</div>
    </div>
    <!-- amount/value cell -->
  </div>
</div>
```
For "Sin talento asignado" (D-17, UI-SPEC line 106): last row, `rank-num` shows `—` (no gold/silver/bronze class), avatar uses `--bg5` background with `?` glyph.

**Funnel row markup** (mockup script template, used to derive the static structure):
```html
<div class="funnel-row">
  <span class="f-label">Llamada</span>
  <div class="f-track">
    <div class="f-fill" style="width:${pct}%;background:${color};"><span>${count}</span></div>
  </div>
  <span class="f-n">${count}</span>
</div>
```

**Activity feed row markup** (mockup):
```html
<div class="card" style="padding:14px 16px;">
  <div class="activity-row">
    <div class="act-icon" style="background:var(--greenD);">✅</div>
    <div class="act-text">
      <div class="act-main"><strong>Doritos MX</strong> — Emicanico pasó a En campaña</div>
      <div class="act-time">Hace 2 horas · Pipedrive</div>
    </div>
  </div>
</div>
```

**Deal row markup (lost opportunities / deals activos, D-25)** (mockup):
```html
<div class="deal-row">
  <div class="deal-l">
    <div class="deal-dot" style="background:${color};"></div>
    <div>
      <div class="deal-brand">${brand}</div>
      <div class="deal-tipo">${tipo}</div>
    </div>
  </div>
  <div class="deal-r">
    <span class="pill" style="background:var(--blueD);color:var(--blueT);">${lossReasonLabel}</span>
  </div>
</div>
```

**Alert markup (bottleneck D-24/D-26, sync-failure banner D-24)** (mockup):
```html
<div class="alert warn">
  <div class="alert-icon">⚠️</div>
  <div class="alert-text"><strong>Cuello de botella detectado:</strong> Solo el {X}% de los deals en {EtapaA} avanzan a {EtapaB}.</div>
</div>
<div class="alert info">
  <div class="alert-icon">💡</div>
  <div class="alert-text">{N} deals llevan más de 14 días sin avanzar de etapa.</div>
</div>
```
Per UI-SPEC line 112, replace mockup's "41% vs 60% industria" copy with the conversion-ratio copy — do NOT carry over "industria"/"promedio de la industria" text.

**`.donut-wrap`/`.donut-legend` (D-26/D-27)** — CSS classes exist in mockup `<style>` but are UNUSED in mockup body (no HTML example to copy). Planner/executor must author new markup using the defined CSS:
```css
.donut-wrap{display:flex;align-items:center;gap:16px;}
.donut-legend{display:flex;flex-direction:column;gap:8px;flex:1;}
```
Pattern: an SVG or CSS `conic-gradient` donut on the left + `.donut-legend` list of `{category label} — {pct}% ({count} deals)` rows on the right, per UI-SPEC line 116 copy contract.

---

### `frontend/js/dashboard.js` (component, request-response — fetch + render)

**Analog:** `frontend/js/auth.js` (full file, 43 lines) — establishes the `apiFetch` 401-interceptor convention that ALL new dashboard fetches must use.

**`apiFetch` pattern** (lines 26-35) — **this is the shared fetch wrapper, reuse verbatim, do not reimplement:**
```javascript
// D-03: global 401 -> redirect-to-login interceptor for use across the dashboard's
// shared JS once Plans 02/03 add authenticated pages.
async function apiFetch(url, options = {}) {
  const res = await fetch(url, { ...options, credentials: "same-origin" });
  if (res.status === 401) {
    window.location.href = "/login.html";
    return;
  }
  return res;
}
```

**Apply to dashboard.js:**
```javascript
async function loadSummary() {
  const res = await apiFetch("/dashboard/summary");
  if (!res) return; // 401 already redirected
  const data = await res.json();
  renderKpis(data.kpis);
  renderRanking(data.ranking);
  renderActivity(data.activity);
}

async function triggerSync() {
  const btn = document.getElementById("sync-btn");
  btn.textContent = "Sincronizando...";
  btn.disabled = true;
  const res = await apiFetch("/sync/pipedrive", { method: "POST" });
  if (!res) return;
  if (res.status === 202) {
    showToast("Sync completado — actualizando...");
    // poll /dashboard/sync-status or reload summary after a delay
  }
  btn.textContent = "Sincronizar ahora";
  btn.disabled = false;
}
```

**Form-submit/credentials pattern** (lines 1-24, for reference on `credentials: "same-origin"` convention — already encapsulated in `apiFetch`, no need to duplicate):
```javascript
const res = await fetch("/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
  body: formData,
  credentials: "same-origin",
});
```

---

### `frontend/css/styles.css` (config, transform — CSS)

**Analog:** `frontend/css/styles.css` (full file, 142 lines) for the existing `:root` token block and `.card`/`.btn` conventions; `.planning/reference/mockup.html` `<style>` block (37.5KB total, extract only the classes listed below) for the NEW component classes.

**Existing `:root` token block** (lines 7-18) — DO NOT redefine, mockup uses identical variable names:
```css
:root {
  --bg:#0c0c0e; --bg2:#111114; --bg3:#18181c; --bg4:#1f1f24; --bg5:#26262c;
  --border:rgba(255,255,255,0.06); --borderM:rgba(255,255,255,0.11); --borderH:rgba(255,255,255,0.18);
  --text:#eeede6; --text2:#8a8980; --text3:#4e4e4a;
  --accent:#e8520a; --accentD:rgba(232,82,10,0.12); --accentB:rgba(232,82,10,0.25);
  --green:#1a9e6e; --greenD:rgba(26,158,110,0.12); --greenT:#3dcf96;
  --amber:#c97c14; --amberD:rgba(201,124,20,0.12); --amberT:#f0a93a;
  --blue:#2472c8; --blueD:rgba(36,114,200,0.12); --blueT:#6aabf0;
  --purple:#6b54d6; --purpleD:rgba(107,84,214,0.12); --purpleT:#a594f0;
  --red:#c43232; --redD:rgba(196,50,50,0.12); --redT:#f07070;
  --r:10px; --rL:14px; --rXL:18px;
}
```

**Existing `.card` (lines 34-40) — MUST be edited per UI-SPEC, not just copied:**
```css
.card {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: var(--rL);
  padding: 18px;        /* UI-SPEC: change to 16px for Phase 2 contract */
  margin-bottom: 12px;
}
```
**Executor action (per UI-SPEC line 53):** change `padding: 18px` → `padding: 16px` (one-line edit, affects login page negligibly).

**New component classes to port from mockup `<style>` (verbatim values, found via grep against `.planning/reference/mockup.html`):**
```css
.kpi-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.kpi-val{font-size:26px;font-weight:500;letter-spacing:-0.5px;font-family:'DM Mono',monospace;margin:6px 0 4px;}  /* UI-SPEC: 600 -> 500 */
.kpi-label{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:0.6px;font-weight:500;}
.kpi-sub{font-size:11px;color:var(--text3);}
.rank-row{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);}
.rank-num{font-size:13px;font-weight:600;font-family:'DM Mono',monospace;color:var(--text3);width:18px;flex-shrink:0;}
.rank-avatar{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;flex-shrink:0;}
.bar-chart{display:flex;align-items:flex-end;gap:8px;height:100px;margin-bottom:8px;}
.bar-col{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;}
.bar-fill{width:100%;border-radius:4px 4px 0 0;transition:height 0.8s cubic-bezier(0.4,0,0.2,1);}
.funnel-row{display:flex;align-items:center;gap:10px;margin-bottom:9px;}
.f-track{flex:1;height:22px;background:var(--bg5);border-radius:5px;overflow:hidden;}
.f-fill{height:100%;border-radius:5px;display:flex;align-items:center;justify-content:flex-end;padding-right:8px;transition:width 0.8s cubic-bezier(0.4,0,0.2,1);}
.f-label{font-size:12px;color:var(--text2);width:130px;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.f-n{font-family:'DM Mono',monospace;font-size:12px;color:var(--text2);width:22px;text-align:right;flex-shrink:0;}
.deal-row{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border);}
.deal-l{display:flex;align-items:center;gap:10px;}
.deal-r{text-align:right;}
.deal-amt{font-size:13px;font-weight:500;font-family:'DM Mono',monospace;}  /* heading role = 500 per UI-SPEC */
.deal-brand{font-size:13px;font-weight:500;}
.deal-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}
.deal-tipo{font-size:11px;color:var(--text3);margin-top:1px;}
.pill{font-size:11px;padding:2px 8px;border-radius:20px;font-weight:500;display:inline-block;margin-top:3px;}
.activity-row{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);}
.act-icon{width:30px;height:30px;border-radius:var(--r);display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;margin-top:1px;}
.act-main{font-size:13px;}
.act-time{font-size:11px;color:var(--text3);margin-top:2px;}
.alert{display:flex;gap:10px;align-items:flex-start;padding:12px 14px;border-radius:var(--r);margin-bottom:10px;}
.donut-wrap{display:flex;align-items:center;gap:16px;}
.donut-legend{display:flex;flex-direction:column;gap:8px;flex:1;}
.talent-selector{display:flex;overflow-x:auto;gap:10px;padding:16px;scrollbar-width:none;}
.talent-card{flex-shrink:0;display:flex;flex-direction:column;align-items:center;gap:8px;padding:14px 16px;background:var(--bg3);border:1px solid var(--border);border-radius:var(--rL);cursor:pointer;transition:all 0.2s;min-width:90px;}
.tc-avatar{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:600;}
.tc-name{font-size:12px;font-weight:500;text-align:center;white-space:nowrap;}
.tc-deals{font-size:11px;color:var(--text3);font-family:'DM Mono',monospace;}
.section{padding:0 16px 16px;}
.section-title{font-size:11px;font-weight:500;text-transform:uppercase;letter-spacing:0.8px;color:var(--text3);margin-bottom:12px;padding-top:4px;}
.live-pill{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--text2);font-family:'DM Mono',monospace;}
.live-dot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 2s infinite;}
.sel{appearance:none;background:var(--bg4);border:1px solid var(--borderM);border-radius:var(--r);padding:6px 28px 6px 10px;font-size:12px;font-family:'DM Sans',sans-serif;color:var(--text); /* + background-image arrow, see mockup */}
.tabbar{display:flex;overflow-x:auto;gap:4px;padding:12px 16px;background:var(--bg2);border-bottom:1px solid var(--border);scrollbar-width:none;position:sticky;top:57px;z-index:99;}
.tab{flex-shrink:0;font-size:13px;font-weight:500;padding:7px 14px;border-radius:20px;border:1px solid var(--border);background:transparent;color:var(--text2);cursor:pointer;transition:all 0.15s;white-space:nowrap;}
.nav-right{display:flex;align-items:center;gap:10px;}
```

**Critical UI-SPEC deviations from the mockup verbatim values (executor must apply these edits when porting):**
1. `.kpi-val { font-weight: 600 }` → **500** (2-weight typography contract).
2. `.card { padding: 18px }` → **16px** (8-point spacing contract).
3. `.kpi { padding: 14px 16px }` (mockup inline style) → **12px 16px** (8-point spacing contract) wherever `.kpi` tiles are rendered.
4. `.deal-amt`/similar "Heading" role classes at weight 600 in mockup → **500** if introduced as new Phase 2 elements (existing micro-exceptions like `.rank-num`/`.f-n` at 600 are pre-existing and NOT changed per UI-SPEC line 71).

---

## Shared Patterns

### Authentication / Authorization
**Source:** `app/routers/talents.py` lines 15-19 + `app/auth/dependencies.py` (full file, 40 lines)
**Apply to:** `app/routers/dashboard.py`, `app/routers/sync.py` — every new router.
```python
from app.auth.dependencies import get_current_user

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)
```
`get_current_user` reads the `access_token` HttpOnly cookie (NOT a Bearer header — Phase 1 deviation from generic FastAPI tutorials), decodes via PyJWT with explicit `algorithms=[ALGORITHM]` allowlist, and raises `401` if missing/invalid. No changes needed — import and apply via `dependencies=[...]` exactly as `talents.py` does.

### Database Session Access
**Source:** `app/database.py` (full file, 34 lines)
**Apply to:** all new routers (via `Depends(get_db)`), `app/sync/jobs.py` / `app/sync/scheduler.py` (via direct `SessionLocal()` + `try/finally: db.close()`), `app/scripts/match_talent_products.py` (via `session_factory=SessionLocal` parameter for testability).
```python
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
Background/scheduled code (no FastAPI request context) uses the `seed_talents.py`/`seed_admin.py`-style `db = SessionLocal(); try: ... finally: db.close()` form directly, not `Depends(get_db)`.

### Error Handling
**Source:** `app/routers/talents.py` lines 36-41 (404 pattern); no `IntegrityError`/global exception handler exists in the codebase (confirmed gap, per prior observation: "No CORS/CSRF handling and no IntegrityError handling found in Phase 1 routers").
**Apply to:** `app/routers/dashboard.py` for any `{id}`-keyed lookups (`GET /dashboard/talents/{id}`):
```python
talent = db.get(Talent, talent_id)
if talent is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talent not found")
```
For `app/sync/jobs.py`, error handling is NEW to this phase — wrap the entire sync body in `try/except Exception as exc:` and persist `SyncLog.status = "error"`, `SyncLog.error_message = str(exc)` (RESEARCH.md Pattern 3 schema + Security Domain note: never log `exc` in a way that could leak `x-api-token` header — use `str(exc)`, not `repr(response.request)`).

### Response Model Conventions
**Source:** `app/schemas/talent.py` (full file, 38 lines)
**Apply to:** `app/schemas/dashboard.py` — `model_config = {"from_attributes": True}` for ORM-backed reads, plain `BaseModel` for service-computed aggregates, `field: T | None = None` for optional fields.

### Frontend Fetch Wrapper
**Source:** `frontend/js/auth.js` lines 26-35 (`apiFetch`)
**Apply to:** `frontend/js/dashboard.js` — every `fetch()` call to `/dashboard/*` and `/sync/*` MUST go through `apiFetch()` (already defines the 401 → `/login.html` redirect; do not duplicate this logic).

### Test Fixtures
**Source:** `tests/conftest.py` (full file, 101 lines) — `client`, `auth_client`, `db_session`, `seed_test_user` fixtures; `tests/test_talents.py` (full file, 93 lines) for endpoint-test structure.
**Apply to:** all 5 new test files (`test_pipedrive_integration.py`, `test_sync.py`, `test_kpis.py`, `test_funnel.py`, `test_dashboard.py`).
```python
def test_talents_require_auth(client):
    response = client.get("/talents")
    assert response.status_code == 401
```
Every new `/dashboard/*` and `/sync/*` endpoint test MUST include an equivalent `test_<endpoint>_requires_auth(client)` using the unauthenticated `client` fixture (per RESEARCH.md Security Domain: "verify with a test asserting 401 without a valid session cookie"). Authenticated tests use `auth_client`. New fixtures needed in `conftest.py`: seeded `Talent`/`TalentProduct`/`Deal`/`DealStageEvent`/`SyncLog` rows, and an `httpx.MockTransport`-based fixture for `PipedriveClient` tests (RESEARCH.md Wave 0 Gaps).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/integrations/pipedrive.py` (httpx v2 client specifics) | service | request-response + batch | No prior httpx integration exists in the codebase (Phase 1 has zero external API calls). RESEARCH.md Pattern 1/2/Code Examples are the primary source — cross-referenced against official Pipedrive v2 docs (HIGH confidence). |
| `app/sync/scheduler.py` (APScheduler + FastAPI lifespan) | service | event-driven | No scheduled/background job exists in Phase 1 (`app/main.py` has no `lifespan`). RESEARCH.md's lifespan example is the primary source. |
| `frontend/*` donut chart markup (`.donut-wrap`/`.donut-legend` HTML structure) | component | transform | CSS classes exist in mockup `<style>` but are unused in mockup `<body>` — no HTML structure to copy. New markup must be authored against the existing CSS class names per UI-SPEC D-26/D-27 copy contract. |
| `app/scripts/match_talent_products.py` (rapidfuzz usage) | script | batch | No fuzzy-matching code exists in the codebase. RESEARCH.md's full skeleton (Code Examples section) is the primary source, combined with `seed_talents.py`/`seed_admin.py`'s session/idempotency conventions (mapped above). |

---

## Metadata

**Analog search scope:** `app/` (models, routers, schemas, auth, scripts, services, integrations, database, config, main), `alembic/versions/`, `frontend/` (css, js, html), `tests/`, `.planning/reference/mockup.html`

**Files scanned:**
- `app/models.py`, `app/database.py`, `app/config.py`, `app/main.py`
- `app/routers/talents.py`, `app/routers/health.py`
- `app/auth/dependencies.py`, `app/auth/router.py`, `app/auth/security.py`
- `app/schemas/talent.py`
- `app/scripts/seed_talents.py`, `app/scripts/seed_admin.py`
- `alembic/versions/324116cbf0dd_initial_schema_users_talents_talent_.py`, `alembic/env.py`
- `frontend/css/styles.css`, `frontend/js/auth.js`, `frontend/login.html`
- `tests/conftest.py`, `tests/test_talents.py`, `tests/test_health.py`
- `.planning/reference/mockup.html` (CSS `<style>` block + body markup for `.kpi-grid`, `.rank-row`, `.funnel-row`, `.deal-row`, `.activity-row`, `.alert`, nav/tabbar)

**Pattern extraction date:** 2026-06-12
</content>
