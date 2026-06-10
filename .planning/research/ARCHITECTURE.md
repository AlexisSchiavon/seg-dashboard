# Architecture Research

**Domain:** Talent-agency commercial intelligence dashboard — modular FastAPI monolith integrating Pipedrive, Google Sheets, Trello, and Claude AI
**Researched:** 2026-06-09
**Confidence:** HIGH (FastAPI/JWT patterns, official docs verified) / MEDIUM (Pipedrive/Trello sync strategy, multi-source community verification)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Vanilla JS)                        │
│   index.html + 5 tabs (Resumen / Talento / Funnel / Leads / Reportes)│
└───────────────────────────────┬───────────────────────────────────--┘
                                  │ fetch() + Bearer JWT
┌─────────────────────────────────────────────────────────────────────┐
│                          ROUTERS (API layer)                         │
│  auth.py  dashboard.py  talents.py  leads.py  reports.py             │
│  - Parse request, validate input (Pydantic), check auth dependency   │
│  - Call services/, shape response (Pydantic schemas)                 │
├─────────────────────────────────────────────────────────────────────┤
│                    SERVICES (business logic layer)                   │
│  funnel.py   kpis.py   reports.py   agent.py                         │
│  - Pure(ish) business logic, reads/writes via models + db session    │
│  - Orchestrates integrations/ for fresh data when needed             │
│  - Talent-agnostic: operates on Talent records from DB, not hardcode │
├─────────────────────────────────────────────────────────────────────┤
│                  INTEGRATIONS (external adapters)                    │
│  pipedrive.py   sheets.py   trello.py   claude.py (M5/M6)            │
│  - Auth + HTTP calls to external APIs                                │
│  - Normalize external shapes → internal dataclasses/Pydantic models  │
│  - NO business logic, NO DB writes (return normalized data only)     │
├─────────────────────────────────────────────────────────────────────┤
│                     SYNC LAYER (M2+, scheduled)                      │
│  app/sync/ (or services/sync.py) + APScheduler                       │
│  - Calls integrations/, upserts into local DB tables                 │
│  - Runs on interval (e.g. every 15 min) + on-demand "Refresh" button │
├─────────────────────────────────────────────────────────────────────┤
│                       DATA LAYER (SQLAlchemy)                        │
│  models.py (Talent, Deal, Lead, Campaign, FunnelStage, SyncLog, User)│
│  database.py (engine, session factory)                               │
│  seg.db (SQLite, single file)                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `routers/` | HTTP boundary: auth check, request validation, response shaping | FastAPI `APIRouter`, Pydantic schemas, `Depends(get_current_user)` |
| `services/` | Business logic: funnel math, KPI aggregation, report assembly, agent orchestration | Plain Python modules/classes, take a DB `Session` + params, return domain objects |
| `integrations/` | External API adapters: auth, HTTP calls, pagination, normalization | One class per provider (`PipedriveClient`, `SheetsClient`, `TrelloClient`), `httpx.Client`, return normalized dataclasses |
| `sync/` (new, recommend adding) | Scheduled/on-demand jobs that call integrations and upsert into DB | APScheduler job + manual `/sync/run` admin endpoint |
| `models.py` | SQLAlchemy ORM models — single source of truth for internal data shape | SQLAlchemy 2.0 declarative models |
| `database.py` | Engine/session lifecycle | SQLAlchemy `sessionmaker`, FastAPI dependency `get_db()` |

## Recommended Project Structure

```
app/
├── main.py                  # App factory, router registration, startup/shutdown (scheduler)
├── config.py                # Pydantic Settings — env vars, talent config path
├── database.py              # engine, SessionLocal, get_db() dependency, Base
├── models.py                # SQLAlchemy models: Talent, Deal, FunnelStage, Lead, Campaign, User, SyncLog
├── schemas/                 # Pydantic request/response models (split from models.py early)
│   ├── auth.py
│   ├── talent.py
│   ├── funnel.py
│   └── reports.py
├── auth/                     # M1 — isolated auth module
│   ├── security.py          # password hashing, JWT encode/decode
│   ├── dependencies.py       # get_current_user, require_auth
│   └── router.py             # /auth/login, /auth/refresh
├── integrations/
│   ├── base.py               # shared httpx client config, retry/backoff helper
│   ├── pipedrive.py           # PipedriveClient: deals, products, custom fields → normalized dicts
│   ├── sheets.py               # SheetsClient: gspread wrapper → normalized lead rows
│   ├── trello.py                # TrelloClient: boards/cards → normalized campaign cards
│   └── claude.py                 # (M5/M6) Anthropic client wrapper
├── sync/                       # NEW — recommend adding in M2
│   ├── scheduler.py             # APScheduler setup (lifespan-managed)
│   └── jobs.py                  # sync_pipedrive(), sync_sheets(), sync_trello()
├── services/
│   ├── funnel.py               # funnel stage aggregation, bottleneck detection
│   ├── kpis.py                  # revenue, ranking, projections (uses Talent.commission_pct)
│   ├── reports.py                # PDF generation orchestration (M5)
│   └── agent.py                   # NL agent tool-calling orchestration (M6)
├── routers/
│   ├── dashboard.py              # /dashboard/summary, /dashboard/funnel
│   ├── talents.py                  # /talents, /talents/{id}, /talents/{id}/kpis
│   ├── leads.py                     # /leads (Sheets-backed)
│   └── reports.py                    # /reports, /reports/{id}/download
└── data/
    └── talents.json (or seed via Alembic/SQL) # initial 21-talent catalog
```

### Structure Rationale

- **`integrations/` returns normalized internal types, never raw API JSON** — this is the seam that makes M2-M4 independently testable (mock the client, not the HTTP layer) and isolates Pipedrive/Trello/Sheets quirks (40-char custom field hashes, gspread row formats, Trello card JSON) from the rest of the app.
- **`sync/` as a separate concern from `integrations/`** — integrations are stateless adapters; sync is the stateful orchestration that decides *when* to call them and *how* to persist results. Splitting these means M2 can ship "on-demand fetch" first and "scheduled sync" can be added without touching `integrations/pipedrive.py`.
- **`schemas/` split from `models.py` early** — even though the predefined structure has a flat `models.py`, add a `schemas/` package on day one (M1) for Pydantic I/O models. This avoids a painful refactor when M2-M4 each add request/response shapes; `models.py` stays pure SQLAlchemy.
- **`auth/` as its own package, not a single file** — JWT logic (token creation/validation), password hashing, and the `get_current_user` dependency are reused by every router from M1 onward. Isolating them means M2-M7 routers only ever import `from app.auth.dependencies import get_current_user` — zero rework.
- **Talent data lives in `models.py` (DB table), seeded from `data/talents.json`** — config-driven extensibility (per project constraint) without hardcoding talent names anywhere in `services/` or `integrations/`.

## Architectural Patterns

### Pattern 1: Adapter + Normalization (integrations/ layer)

**What:** Each integration module exposes a client class with methods that return **internal dataclasses/Pydantic models**, never raw provider JSON. All field-mapping, custom-field-hash resolution, and pagination happen inside the adapter.

**When to use:** Always, for every external API (Pipedrive, Sheets, Trello, Claude).

**Trade-offs:** Slightly more upfront code (mapping functions) but pays off immediately — `services/funnel.py` and `services/kpis.py` never need to know Pipedrive's 40-character custom field hashes or Trello's nested `idList`/`labels` structure.

**Example:**
```python
# app/integrations/pipedrive.py
from dataclasses import dataclass
from datetime import date
import httpx
from app.config import settings

@dataclass
class NormalizedDeal:
    pipedrive_id: int
    title: str
    value: float
    currency: str
    stage_name: str
    talent_product_id: int | None
    loss_reason: str | None
    brand_category: str | None
    expected_collection_date: date | None
    status: str  # open / won / lost

class PipedriveClient:
    BASE_URL = "https://{domain}.pipedrive.com/api/v2"

    def __init__(self, api_token: str, domain: str):
        self._client = httpx.Client(
            base_url=self.BASE_URL.format(domain=domain),
            params={"api_token": api_token},
            timeout=30.0,
        )
        # custom field key → readable name, fetched once and cached
        self._field_map = self._load_field_map()

    def _load_field_map(self) -> dict[str, str]:
        resp = self._client.get("/dealFields")
        resp.raise_for_status()
        return {f["key"]: f["name"] for f in resp.json()["data"]}

    def get_deals(self, since: date | None = None) -> list[NormalizedDeal]:
        """Fetch deals, paginate, normalize. Pure function of inputs -> outputs."""
        deals: list[NormalizedDeal] = []
        cursor = None
        while True:
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            resp = self._client.get("/deals", params=params)
            resp.raise_for_status()
            payload = resp.json()
            for raw in payload["data"] or []:
                deals.append(self._normalize_deal(raw))
            cursor = payload.get("additional_data", {}).get("next_cursor")
            if not cursor:
                break
        return deals

    def _normalize_deal(self, raw: dict) -> NormalizedDeal:
        # Resolve custom field hashes via self._field_map by name lookup
        loss_reason_key = self._key_for("Razón de pérdida")
        brand_cat_key = self._key_for("Categoría de marca")
        collection_date_key = self._key_for("Fecha de cobro esperada")
        return NormalizedDeal(
            pipedrive_id=raw["id"],
            title=raw["title"],
            value=float(raw.get("value") or 0),
            currency=raw.get("currency", "MXN"),
            stage_name=raw.get("stage_id", {}).get("name", "Unknown")
                if isinstance(raw.get("stage_id"), dict) else str(raw.get("stage_id")),
            talent_product_id=self._extract_product_id(raw),
            loss_reason=raw.get(loss_reason_key),
            brand_category=raw.get(brand_cat_key),
            expected_collection_date=raw.get(collection_date_key),
            status=raw.get("status", "open"),
        )

    def _key_for(self, field_name: str) -> str | None:
        for key, name in self._field_map.items():
            if name == field_name:
                return key
        return None

    def _extract_product_id(self, raw: dict) -> int | None:
        products = raw.get("products") or []
        return products[0]["product_id"] if products else None
```

### Pattern 2: Sync Job + Local Cache (SQLite as source of truth for the dashboard)

**What:** A scheduled job (APScheduler, run inside FastAPI's lifespan) calls each `integrations/*Client`, normalizes results, and **upserts** into local SQLAlchemy tables (`Deal`, `Lead`, `Campaign`). All dashboard reads (`routers/dashboard.py`, `routers/talents.py`) query the local DB — never call external APIs synchronously on a page load.

**When to use:** M2 onward. Start simple: interval-based polling (every 15-30 min) is sufficient for an internal dashboard with 21 talents and a small sales team — far below Pipedrive's token budget and Trello's 300 req/10s limit. Add an admin "Sync now" button (`POST /sync/run`) for on-demand refresh.

**Trade-offs:**
- Polling is simpler to build and test than webhooks, requires no public HTTPS endpoint during M2-M4 (before Docker/EasyPanel deploy in M7), and is well within both Pipedrive's and Trello's rate limits at this data volume.
- Webhooks (Pipedrive supports free webhooks; Trello supports unlimited webhooks) are *more real-time* and token-free, but require a stable public URL — only available after M7 deploy. **Recommendation: ship polling in M2-M4, consider adding webhooks as a post-M7 enhancement** once the app has a permanent EasyPanel URL. Document this as a deferred optimization, not a blocker.
- A `SyncLog` table (timestamp, source, status, records_synced, error) gives the dashboard a "last updated" indicator and surfaces sync failures — cheap to add, high UX value.

**Example:**
```python
# app/sync/jobs.py
from datetime import datetime
from sqlalchemy.orm import Session
from app.integrations.pipedrive import PipedriveClient
from app.models import Deal, SyncLog, Talent
from app.config import settings

def sync_pipedrive(db: Session) -> SyncLog:
    client = PipedriveClient(settings.PIPEDRIVE_API_TOKEN, settings.PIPEDRIVE_DOMAIN)
    log = SyncLog(source="pipedrive", started_at=datetime.utcnow(), status="running")
    db.add(log)
    db.commit()

    try:
        deals = client.get_deals()
        # Map Pipedrive product_id -> internal Talent via Talent.pipedrive_product_id
        talent_by_product = {
            t.pipedrive_product_id: t for t in db.query(Talent).all()
            if t.pipedrive_product_id
        }
        for nd in deals:
            existing = db.query(Deal).filter_by(pipedrive_id=nd.pipedrive_id).first()
            talent = talent_by_product.get(nd.talent_product_id)
            if existing:
                _update_deal_from_normalized(existing, nd, talent)
            else:
                db.add(Deal.from_normalized(nd, talent))
        log.status = "success"
        log.records_synced = len(deals)
    except Exception as e:
        log.status = "error"
        log.error_message = str(e)
    finally:
        log.finished_at = datetime.utcnow()
        db.commit()
    return log
```

```python
# app/sync/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import SessionLocal
from app.sync.jobs import sync_pipedrive, sync_sheets, sync_trello

scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.add_job(_run_pipedrive_sync, "interval", minutes=15, id="sync_pipedrive")
    scheduler.add_job(_run_sheets_sync, "interval", minutes=30, id="sync_sheets")
    scheduler.add_job(_run_trello_sync, "interval", minutes=15, id="sync_trello")
    scheduler.start()

def _run_pipedrive_sync():
    with SessionLocal() as db:
        sync_pipedrive(db)

# main.py lifespan: start_scheduler() on startup, scheduler.shutdown() on stop
```

### Pattern 3: Talent as Data-Driven Entity (mapping table, not hardcoded)

**What:** `Talent` is a SQLAlchemy table with a stable internal `id`, plus **nullable foreign keys/identifiers into each external system** (`pipedrive_product_id`, `sheets_label`/tag value, `trello_label_id` or board mapping). All integrations resolve "which talent does this record belong to" by looking up these mapping columns — never by matching on talent name strings scattered through code.

**When to use:** From M2 onward. Seed the 21 current talents via a one-time script or `data/talents.json` loaded on first run / via a `/admin/seed-talents` endpoint or Alembic data migration.

**Trade-offs:** Requires one-time manual mapping work (matching each talent to their Pipedrive product ID, Sheets tag, Trello board/label) — but this is a config task, not a code task, satisfying the "add talents without touching code" constraint.

**Example:**
```python
# app/models.py
class Talent(Base):
    __tablename__ = "talents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    slug: Mapped[str] = mapped_column(String, unique=True)  # for URLs/config keys
    commission_pct: Mapped[float] = mapped_column(default=0.70)
    active: Mapped[bool] = mapped_column(default=True)

    # External system mappings — nullable, filled in via admin/config
    pipedrive_product_id: Mapped[int | None] = mapped_column(nullable=True)
    sheets_tag: Mapped[str | None] = mapped_column(nullable=True)   # value used in Sheets "talento" column
    trello_label_id: Mapped[str | None] = mapped_column(nullable=True)

    deals: Mapped[list["Deal"]] = relationship(back_populates="talent")
    leads: Mapped[list["Lead"]] = relationship(back_populates="talent")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="talent")
```

```json
// data/talents.json — seed file, loaded by a one-time script (not at every startup)
[
  {"name": "Navarretes Show", "slug": "navarretes-show", "pipedrive_product_id": null, "sheets_tag": "Navarretes", "trello_label_id": null},
  {"name": "Don Silverio", "slug": "don-silverio", "pipedrive_product_id": null, "sheets_tag": "Don Silverio", "trello_label_id": null}
]
```

## Data Flow

### Request Flow (dashboard read)

```
Browser (fetch + Bearer JWT)
    ↓
routers/talents.py (Depends(get_current_user) → 401 if invalid)
    ↓
services/kpis.py (query Deal/Talent tables, compute revenue/ranking/projection)
    ↓
database.py session → SQLite (seg.db)
    ↓
Pydantic response schema → JSON
    ↓
Frontend renders into mockup-derived HTML
```

### Sync Flow (background, M2+)

```
APScheduler trigger (every 15 min) OR admin "Sync now" button
    ↓
sync/jobs.py: sync_pipedrive() / sync_sheets() / sync_trello()
    ↓
integrations/pipedrive.py: PipedriveClient.get_deals() → list[NormalizedDeal]
    ↓
sync/jobs.py: resolve Talent via mapping columns, upsert into Deal table
    ↓
SyncLog row written (status, timestamp, count)
    ↓
(Dashboard reads always hit local DB — never blocked on external API latency)
```

### Automation Flow (Pipedrive won → Trello card, M4)

```
Sync detects Deal.status changed to "won" (compare against previous synced state)
    ↓
services/funnel.py (or a dedicated automation service) triggers
    ↓
integrations/trello.py: TrelloClient.create_card(talent, deal, expected_collection_date)
    ↓
Local Campaign record created, linked to Deal + Talent
```

### Key Data Flows

1. **Pipedrive → Deal/Talent (M2):** `PipedriveClient.get_deals()` normalizes raw deals; sync job maps `talent_product_id` → `Talent.id` via `pipedrive_product_id`; upserts `Deal` rows. `services/funnel.py` and `services/kpis.py` read only from `Deal`/`Talent` tables.
2. **Sheets → Lead (M3):** `SheetsClient.get_leads()` reads rows from the Gmail-fed sheet, normalizes columns (talent, source, status) into `NormalizedLead`; sync job maps `sheets_tag` → `Talent.id`, upserts `Lead` rows.
3. **Trello → Campaign (M4):** `TrelloClient.get_cards()` reads cards from configured boards (`TRELLO_BOARD_IDS`), normalizes into `NormalizedCampaignCard` (execution vs. collection status, due dates); sync job maps to `Talent` via label/board, upserts `Campaign` rows.
4. **Won deal → Trello card (M4, reverse flow):** the only flow where the system *writes* to an external API — isolate this in its own function (`integrations/trello.py: create_card()`) called by a service-layer "automation" function, triggered post-sync when a deal transitions to "won".
5. **Reports (M5):** `services/reports.py` queries already-synced local data (no live API calls), assembles a prompt/context, calls `integrations/claude.py` to generate PDF content, stores result + metadata in a `Report` table.
6. **NL Agent (M6):** `services/agent.py` exposes a small set of "tools" (functions that query `services/funnel.py`, `services/kpis.py`) to Claude via tool-calling; agent never queries external APIs directly — always through the local DB via services.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Current (21 talents, ~5-10 internal users) | SQLite + APScheduler in-process is correct. Single container, single SQLite file, polling every 15-30 min. |
| Growth (50-100 talents, more frequent updates needed) | Add Pipedrive/Trello webhooks (now feasible post-M7 deploy with stable URL) to reduce polling lag to near-real-time; SQLite still fine at this volume. |
| Multi-agency / OpenClaw (future, explicitly out of scope now) | `integrations/` and `services/` layers are already provider-agnostic enough to be extracted into a shared package consumed by multiple agent modules; `Talent` table model generalizes to a `client_id`/tenant-scoped entity if multi-tenant is ever needed — but this is NOT a concern for current build order. |

### Scaling Priorities

1. **First "bottleneck":** SQLite write contention if sync jobs and dashboard reads collide during sync — mitigate with WAL mode (`PRAGMA journal_mode=WAL`) from day one in `database.py`. Trivial to set up now, painful to retrofit.
2. **Second consideration:** APScheduler jobs running in-process means a container restart briefly pauses sync — acceptable for an internal tool; if it becomes an issue, the `sync/` module can be extracted to a separate process/cron without touching `integrations/` or `services/`.

## Anti-Patterns

### Anti-Pattern 1: Calling external APIs directly from routers or services on every request

**What people do:** `routers/dashboard.py` calls `PipedriveClient.get_deals()` synchronously on every page load to "always show fresh data."

**Why it's wrong:** Slow page loads (network round-trip to Pipedrive/Sheets/Trello on every dashboard view), burns API rate-limit budget fast, and breaks the moment any external API is down or slow — the whole dashboard becomes unusable.

**Do this instead:** All reads come from the local SQLite cache populated by `sync/`. Provide a visible "last synced" timestamp and an explicit "Sync now" action for users who want fresher data.

### Anti-Pattern 2: Hardcoding talent names/IDs in business logic or integration code

**What people do:** `if talent_name == "Navarretes Show": ...` scattered across `services/` or `integrations/` to handle "special cases" per talent.

**Why it's wrong:** Directly violates the "add talents via config, not code" requirement; every new talent or special case becomes a code change and deploy.

**Do this instead:** All talent-specific data (commission %, external IDs, categories) lives in the `Talent` table / `data/talents.json`. Business logic (`services/kpis.py`) is generic — it operates on `Talent.commission_pct`, `Talent.pipedrive_product_id`, etc., never on talent names as conditionals.

### Anti-Pattern 3: Mixing Pydantic API schemas with SQLAlchemy ORM models

**What people do:** Use the same class for both DB persistence and API request/response, or return ORM objects directly from route handlers.

**Why it's wrong:** Couples your API contract to your DB schema — a column rename breaks the frontend; lazy-loading relationships can leak DB sessions or cause serialization errors (especially with FastAPI's automatic JSON encoding of SQLAlchemy objects).

**Do this instead:** Keep `models.py` (SQLAlchemy) and `schemas/*.py` (Pydantic) separate from M1. Routers always return Pydantic schemas (`response_model=...`), converted from ORM objects via `model_validate()` (Pydantic v2, with `from_attributes=True`).

### Anti-Pattern 4: Building webhook receivers before the app has a stable public URL

**What people do:** Implement Pipedrive/Trello webhook endpoints in M2-M4 "to be real-time from the start."

**Why it's wrong:** M2-M4 happen before M7 (Docker/EasyPanel deploy) — there's no stable public HTTPS endpoint to register webhooks against during local development, leading to wasted effort, ngrok hacks, and untestable code paths.

**Do this instead:** Ship polling-based sync in M2-M4 (well within rate limits at this scale). Revisit webhooks as a post-M7 enhancement once a permanent URL exists — the `sync/` module's job functions can be triggered by either a scheduler tick or a webhook handler with no change to `integrations/` or `services/`.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Pipedrive | `integrations/pipedrive.py` — `httpx.Client`, token-based rate limit (30k tokens/day base × plan multiplier × seats), v2 API recommended | Custom fields are 40-char hashes — resolve via `/dealFields` once and cache the name→key map. Polling every 15 min is far under the daily token budget at 21-talent scale. |
| Google Sheets | `integrations/sheets.py` — `gspread` + `google-auth` service account | Read-only access sufficient (leads come from Gmail into the sheet by an existing process). No rate-limit concern at this volume; poll every 30 min. |
| Trello | `integrations/trello.py` — `httpx` or `py-trello`, key+token auth | Rate limits: 300 req/10s per API key, 100 req/10s per token — trivial at this scale. Webhooks are unlimited and free but require public URL (defer to post-M7). Write path (card creation on "won" deal) is the only outbound call — wrap in retry logic. |
| Anthropic Claude | `integrations/claude.py` — official `anthropic` Python SDK | M5: synchronous call during report generation (can be slow — consider running as a background task with status polling for PDF generation). M6: tool-calling pattern, agent calls local `services/` functions as tools, not external APIs directly. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `routers/` ↔ `services/` | Direct Python function calls, `Depends(get_db)` session passed through | Routers never touch `models.py` or `integrations/` directly — only through `services/`. |
| `services/` ↔ `integrations/` | Direct Python function calls, only from `sync/` jobs (and the won→Trello automation) | `services/funnel.py`/`kpis.py` should rarely import `integrations/` directly — they read from DB. Only `sync/jobs.py` and the automation service call integration clients. |
| `services/` ↔ `models.py`/`database.py` | SQLAlchemy `Session` passed via dependency injection | Standard FastAPI `get_db()` dependency, used consistently from M1. |
| `auth/` ↔ everything else | `Depends(get_current_user)` imported into every protected router | Established once in M1; M2-M7 routers add this dependency with zero changes to `auth/` itself. |
| Frontend ↔ Backend | REST JSON over HTTPS, `Authorization: Bearer <jwt>` header | Vanilla JS `fetch()`; token stored in `localStorage` or `sessionStorage`, refreshed via `/auth/refresh` if refresh-token pattern is used. |

## JWT Auth Structure (M1) — Designed for Zero Rework in M2-M7

**Recommendation:** Build `auth/` as a self-contained package in M1 with these pieces, none of which need to change as integrations are added:

1. **`auth/security.py`** — `create_access_token()`, `decode_token()`, password hashing (`passlib`/`bcrypt`). Pure functions, no DB dependency beyond reading `User` for login.
2. **`auth/dependencies.py`** — `get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User`. This single dependency is imported by every router from M2 onward (`talents.py`, `leads.py`, `reports.py`, future `agent` endpoints).
3. **`auth/router.py`** — `/auth/login` (returns JWT), optionally `/auth/refresh`. Since "Out of Scope" explicitly excludes role differentiation, **do not build a roles/permissions system in M1** — but do include a `User.role` or `User.is_admin` *column* (even if unused) so that if M7 or a later milestone needs an admin-only `/sync/run` or `/admin/seed-talents` endpoint, it's a query change, not a schema migration.
4. **No integration-specific auth logic belongs in `auth/`.** Pipedrive tokens, Google service account JSON, Trello key/token, and Anthropic API key are all *server-side* credentials in `config.py`/`.env` — completely separate from user-facing JWT auth. This separation is what prevents rework: `auth/` only ever deals with dashboard *user* sessions, never external API credentials.

**Why this unblocks M2-M7 cleanly:** Every new router added in M2 (Pipedrive endpoints), M3 (leads), M4 (Trello/automation), M5 (reports), M6 (agent) follows the identical pattern — `router = APIRouter(dependencies=[Depends(get_current_user)])` or per-route `Depends`. No new auth code is written after M1; only new routes that consume the existing dependency.

## Build Order Implications (M1 → M7)

**M1 decisions that unblock/constrain later modules:**

- **`database.py` + `models.py` base setup must include `Talent`, `User` tables from the start** (even if `Talent` has only `name`/`slug`/`commission_pct` initially) — M2 immediately needs `Talent.pipedrive_product_id` to exist as a column to populate.
- **Enable SQLite WAL mode in `database.py` from M1** — cheap now, prevents write-lock issues once `sync/` jobs run concurrently with dashboard reads (M2+).
- **Establish `schemas/` package in M1**, even if it only holds auth schemas initially — M2-M5 each add response schemas; retrofitting this split later means touching every router.
- **`config.py` should define ALL env vars from `.env.example` up front** (Pipedrive, Sheets, Trello, Anthropic, even though unused until M2/M3/M4/M5) — `pydantic-settings` validates presence at startup, catching config errors early rather than at the M2 integration point.
- **`get_current_user` dependency pattern established in M1** is reused verbatim — confirmed above, zero rework risk.

**M2 decisions that unblock M3/M4:**

- The `integrations/base.py` shared httpx client/retry pattern built for Pipedrive in M2 is directly reused by `sheets.py` (M3) and `trello.py` (M4) — establishing this shared scaffolding in M2 (rather than per-integration ad hoc) saves rework.
- The `sync/` module (scheduler + job pattern + `SyncLog` table) built in M2 for Pipedrive is extended (not redesigned) for Sheets (M3) and Trello (M4) — just new job functions registered with the same scheduler.
- The `Talent` external-mapping pattern (nullable FK columns per provider) established for `pipedrive_product_id` in M2 is extended with `sheets_tag` (M3) and `trello_label_id` (M4) — same table, additive columns only.

**M4 → M5/M6 dependency:** Reports (M5) and the NL agent (M6) both read exclusively from local synced data via `services/`, so they have **no dependency on M2-M4 integration code directly** — only on the data being present in the DB. This means M5/M6 can be developed/tested against seeded/fixture data even before M2-M4 are fully live, if parallelization is ever desired (though the project mandates strict sequential M1→M7).

**M7 (Docker/EasyPanel) implications:** Because `sync/` uses in-process APScheduler (no external cron/Redis dependency), the Dockerfile/docker-compose setup in M7 requires no additional services beyond the FastAPI container itself — keeping deploy simple. SQLite file should be placed on a persistent volume in `docker-compose.yml`.

## Sources

- [FastAPI Modular Monolith Starter Kit (GitHub)](https://github.com/arctikant/fastapi-modular-monolith-starter-kit) — MEDIUM confidence, community reference
- [Modular Monolith FastAPI with SQLModel (GitHub)](https://github.com/YoraiLevi/modular-monolith-fastapi) — MEDIUM confidence
- [Layered Architecture & Dependency Injection in FastAPI (DEV Community)](https://dev.to/markoulis/layered-architecture-dependency-injection-a-recipe-for-clean-and-testable-fastapi-code-3ioo) — MEDIUM confidence
- [FastAPI official docs — SQL Databases](https://fastapi.tiangolo.com/tutorial/sql-databases/) — HIGH confidence
- [FastAPI official docs — Get Current User](https://fastapi.tiangolo.com/tutorial/security/get-current-user/) — HIGH confidence
- [Pipedrive Rate Limiting docs](https://pipedrive.readme.io/docs/core-api-concepts-rate-limiting) — HIGH confidence (official)
- [Pipedrive Custom Fields docs](https://pipedrive.readme.io/docs/core-api-concepts-custom-fields) — HIGH confidence (official)
- [Pipedrive Guide for Optimizing API Usage](https://pipedrive.readme.io/docs/guide-for-optimizing-api-usage) — HIGH confidence (official, recommends webhooks over polling for high-volume use)
- [Trello REST API Rate Limits (Atlassian)](https://developer.atlassian.com/cloud/trello/guides/rest-api/rate-limits/) — HIGH confidence (official)
- [Trello Webhooks docs (Atlassian)](https://developer.atlassian.com/cloud/trello/guides/rest-api/webhooks/) — HIGH confidence (official)
- [Implementing Background Job Scheduling in FastAPI with APScheduler (Medium)](https://rajansahu713.medium.com/implementing-background-job-scheduling-in-fastapi-with-apscheduler-6f5fdabf3186) — MEDIUM confidence

---
*Architecture research for: Talent-agency commercial intelligence dashboard (modular FastAPI monolith)*
*Researched: 2026-06-09*
