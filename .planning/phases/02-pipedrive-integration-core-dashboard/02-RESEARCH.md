# Phase 2: Pipedrive Integration & Core Dashboard - Research

**Researched:** 2026-06-11
**Domain:** Pipedrive REST API integration (sync), APScheduler background jobs in a sync FastAPI/SQLAlchemy app, dashboard KPI/funnel computation, name-based fuzzy matching
**Confidence:** MEDIUM-HIGH (Pipedrive v2 API auth/endpoints verified via official docs + cross-source confirmation; APScheduler/rapidfuzz verified via PyPI + GitHub; bottleneck/activity-feed design choices are research recommendations, not externally verifiable facts)

## Summary

Phase 2 adds a Pipedrive sync layer (`app/integrations/pipedrive.py` + `app/sync/`) and three dashboard tabs backed by real data. The single most important finding — and a correction to the existing `ARCHITECTURE.md` example code — is that **Pipedrive API v2 no longer accepts `?api_token=` as a query parameter; it requires the token in an `x-api-token` HTTP header** `[CITED: pipedrive.readme.io]`. v1 endpoints are past their deprecation grace period (end of 2025) as of June 2026, so this phase should build directly against `/api/v2/deals`, `/api/v2/dealFields`, `/api/v2/deals/products` (bulk), and `/api/v2/products`.

Custom fields in v2 are nested under a `custom_fields` object keyed by the same 40-character hashes as v1 (`{"custom_fields": {"<hash>": {"value": ..., }}}`), confirming PITFALLS.md's field-resolution pattern is still required but the parsing shape changes slightly from v1. Enum/set custom fields (razón de pérdida, categoría de marca) store an **integer option `id`** on the deal — the `dealFields` response provides an `options: [{id, label}]` array per field, so the resolution layer must build a two-level map: field hash → field name, AND per-field option id → label.

For the four open discretion items: (1) **scheduler** — `APScheduler` 3.x `BackgroundScheduler` started/stopped via FastAPI's lifespan context manager, writing through the existing sync `SessionLocal`, matching ARCHITECTURE.md's Pattern 2 exactly; (2) **activity feed** — derive from a lightweight `DealStageEvent` table populated by diffing `stage_id`/`status` during each sync (no per-deal `/flow` calls, which don't scale and aren't bulk-fetchable); (3) **bottleneck detection** — compute stage-to-stage conversion percentages from current-snapshot deal counts per stage (open deals only) and flag the stage with the lowest conversion ratio relative to the next stage, falling back to "no bottleneck detected" if sample size is too small — this is realistically computable from sync snapshots without per-deal stage-history API calls; (4) **auto-match** — a one-time script using `rapidfuzz.process.extractOne` with `WRatio` + `utils.default_process` for normalization, threshold ~85, output a match report for manual review (D-18).

**Primary recommendation:** Build `PipedriveClient` against API v2 with `x-api-token` header auth, paginate all list endpoints via `cursor`/`next_cursor`, resolve custom fields (both hash→name and enum option id→label) once at sync-job start via `/dealFields`, and persist sync state (`Deal`, `DealStageEvent`, `SyncLog`) so all dashboard reads hit local SQLite only.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pipedrive API calls (deals/products/dealFields) | API/Backend (`app/integrations/pipedrive.py`) | — | External adapter; normalizes raw JSON, no business logic, no DB writes |
| Hourly sync + "Sincronizar ahora" orchestration | API/Backend (`app/sync/`) | Database/Storage (writes via SQLAlchemy session) | Stateful job that calls integrations and upserts; scheduler lives in-process per ARCHITECTURE.md Pattern 2 |
| Talent↔product auto-match (one-time script) | API/Backend (`app/scripts/`) | Database/Storage | One-shot script per D-19, writes `talent_products.pipedrive_product_id` |
| Commission (70%) / "Sin cotizar" computation | API/Backend (`app/services/kpis.py`, `app/services/funnel.py`) | Database/Storage (persisted on `Deal` row at sync write time) | See "Don't Hand-Roll" — computed once at sync write, not on every dashboard read |
| Funnel stage aggregation + bottleneck detection | API/Backend (`app/services/funnel.py`) | — | Pure read of local `Deal`/`DealStageEvent` tables |
| Activity feed (DASH-01) | API/Backend (`app/services/funnel.py` or new `app/services/activity.py`) | Database/Storage (`DealStageEvent` table) | Derived during sync, read at dashboard request time |
| Resumen / Por talento / Funnel tab rendering | Browser/Client (Vanilla JS) | API/Backend (`app/routers/dashboard.py`) | Frontend fetches JSON from new dashboard endpoints; no SSR |
| "Última sync" indicator + sync-failure banner | Browser/Client | API/Backend (`SyncLog` exposed via `/dashboard/sync-status` or similar) | D-21/D-24 — frontend polls or reads on page load |
| Donut chart rendering (brand category) | Browser/Client (Vanilla JS + existing `.donut-wrap`/`.donut-legend` CSS) | API/Backend (provides aggregated counts) | D-26/D-27 — backend returns counts per category, frontend draws |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | `>=0.28.1` (already in pyproject.toml) | Pipedrive v2 HTTP client | Project constraint; sync `httpx.Client` with `headers={"x-api-token": ...}` + connection reuse |
| APScheduler | `3.11.2` (verified on PyPI, June 2026) | Hourly Pipedrive sync scheduling | De-facto standard for in-process scheduled jobs in sync Python web apps; `BackgroundScheduler` works with sync SQLAlchemy sessions, no extra infra (Redis/Celery) needed at this scale |
| rapidfuzz | `3.14.5` (verified on PyPI, June 2026) | One-time talent↔product name fuzzy matching (D-16) | `thefuzz`/`fuzzywuzzy`-API-compatible, C++-backed (fast), actively maintained (github.com/rapidfuzz/RapidFuzz), no GPL `python-Levenshtein` dependency issue that `fuzzywuzzy` has |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none new) | — | — | Retry/backoff for Pipedrive 429s should be hand-rolled (a ~15-line loop checking `response.status_code == 429` + `Retry-After` header) rather than adding `tenacity` — at 21-talent scale, hourly sync, well under the daily token budget, a dependency for this is not justified per CLAUDE.md's "thin wrapper, avoid extra deps" philosophy |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| APScheduler `BackgroundScheduler` (in-process) | System cron calling a CLI script | Cron is simpler conceptually but requires a separate process/entrypoint outside the FastAPI app, complicates the Docker/EasyPanel image (M7) with a second cron daemon, and loses easy access to the app's `SessionLocal`/config without re-init. APScheduler in-process matches ARCHITECTURE.md Pattern 2 and keeps M7 deploy single-container. |
| APScheduler `BackgroundScheduler` | FastAPI `BackgroundTasks` (per-request) | `BackgroundTasks` only fires after a request completes — there's no request to attach the hourly trigger to. Usable for the "Sincronizar ahora" on-demand path (D-23 async behavior) but not for the hourly schedule (D-20). Use BOTH: APScheduler for the hourly job, `BackgroundTasks` (or a thread) for the manual "sync now" button so the HTTP response returns immediately. |
| rapidfuzz | `thefuzz` / `fuzzywuzzy` | `fuzzywuzzy` is unmaintained (archived) and pulls in `python-Levenshtein` (GPL) unless `python-Levenshtein` is swapped for `rapidfuzz` anyway — rapidfuzz is the maintained, faster, API-compatible successor. No reason to choose the alternative. |
| Pipedrive API v2 | Pipedrive API v1 | v1 deprecation grace period ended end of 2025 (per Pipedrive's own changelog) — as of June 2026, v1 "availability and functionality will no longer be guaranteed." Build against v2 from the start of M2; do not copy v1-shaped example code from ARCHITECTURE.md verbatim (its auth pattern is v1-only). |

**Installation:**
```bash
uv add apscheduler rapidfuzz
```

**Version verification:**
```bash
$ curl -s https://pypi.org/pypi/apscheduler/json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"
3.11.2
$ curl -s https://pypi.org/pypi/rapidfuzz/json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"
3.14.5
```
Both confirmed live against PyPI on 2026-06-11. `apscheduler`'s source repo is `github.com/agronholm/apscheduler` (first PyPI release `1.0`, long history); `rapidfuzz`'s is `github.com/rapidfuzz/RapidFuzz`.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| apscheduler | PyPI | 15+ yrs (first release `1.0`, long-lived 3.x line) | very high (standard scheduling lib) | github.com/agronholm/apscheduler | [OK] | Approved |
| rapidfuzz | PyPI | 6+ yrs, active (v3.14.5 current) | very high (fuzzywuzzy successor) | github.com/rapidfuzz/RapidFuzz | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

slopcheck 0.6.1 was installed successfully (`pip3 install --user slopcheck`) and ran its registry-scan phase against both packages (`slopcheck install apscheduler rapidfuzz`), returning `[OK]` for both before failing harmlessly on a sandboxed `pip install` subprocess step (irrelevant to the scan verdict). Both package names match training-data knowledge AND are confirmed via PyPI JSON metadata with long-lived, well-known GitHub source repos — `[VERIFIED: npm registry]`-equivalent confidence for PyPI is reached here because both the package identity and the existence/health were corroborated by an authoritative source (PyPI JSON API + GitHub org).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PIPE-01 | Sync Pipedrive deals (stages, value, products, custom fields) into SQLite on schedule + manual "sync now" | v2 `/deals` with `cursor`/`limit=500` pagination + `updated_since` filter for incremental sync; APScheduler `BackgroundScheduler` (hourly, D-20) + `BackgroundTasks`/thread for "sync now" (D-22/D-23); `SyncLog` table for D-21/D-24 |
| PIPE-02 | Map deal product → talent, compute 70% fixed commission per deal | v2 `/deals/{id}/products` (or bulk `/deals/products?deal_ids=...`) gives `product_id`; `talent_products.pipedrive_product_id` (Phase 1 schema) resolves to `Talent`; commission computed at sync-write time in `app/sync/jobs.py` or `services/kpis.py`, stored on `Deal.commission_amount` |
| PIPE-03 | Classify $0 MXN deals as "Sin cotizar" | Computed alongside commission at sync-write time — `Deal.value == 0` → `Deal.status_label = "sin_cotizar"` (or equivalent flag) |
| PIPE-04 | Capture custom fields: razón de pérdida, categoría de marca, fecha de cobro esperada | `/dealFields` (v2) resolution layer: hash→name map + enum option id→label map, built once per sync run; `custom_fields.<hash>.value` parsed per type (enum=int id, date=string) |
| PIPE-05 | Track 6 funnel stages per deal (Llamada → Cotización → Negociación → Contrato → En ejecución → Cobranza) | `deal.stage_id` + `/stages` (or `/pipelines`) to resolve stage_id → stage name/order; `DealStageEvent` table records transitions for activity feed (DASH-01) and bottleneck calc (DASH-03) |
| DASH-01 | Resumen: global KPIs, talent ranking, activity feed | KPIs/ranking computed from local `Deal`/`Talent` join (services/kpis.py); activity feed from `DealStageEvent` ordered by `detected_at desc` |
| DASH-02 | Por talento: KPIs, funnel, lost opportunities (D-25), brand categories (D-26/D-27) | Lost deals = `Deal.status == 'lost'` filtered by talent, grouped by `loss_reason` (resolved custom field); brand category donut = `Deal.brand_category` grouped, % by deal count (D-27) |
| DASH-03 | Funnel completo: 6 stages with count/amount, bottleneck detection | Aggregate `Deal` counts/sums per stage (global); bottleneck = stage-to-stage conversion ratio from current snapshot, flagged if below a fixed internal threshold |
</phase_requirements>

## Architecture Patterns

### System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│  TRIGGER SOURCES                                                       │
│  ┌─────────────────────┐        ┌──────────────────────────────────┐ │
│  │ APScheduler          │        │ POST /sync/pipedrive (D-22)       │ │
│  │ interval=1h (D-20)   │        │ "Sincronizar ahora" → 202 + async │ │
│  └──────────┬───────────┘        └─────────────────┬────────────────┘ │
│             │                                       │                  │
│             ▼                                       ▼                  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │            app/sync/jobs.py :: sync_pipedrive(db)               │  │
│  │  1. Load/refresh field map (dealFields: hash→name,              │  │
│  │     enum option id→label) — cached, short TTL                   │  │
│  │  2. Load pipeline stages (stage_id → name/order)                │  │
│  │  3. Paginate /api/v2/deals (cursor, limit=500,                  │  │
│  │     updated_since=last_sync_time for incremental runs)          │  │
│  │  4. Bulk-fetch products: /api/v2/deals/products?deal_ids=...    │  │
│  │  5. For each deal: normalize, resolve talent via                │  │
│  │     talent_products.pipedrive_product_id (or "Sin talento")     │  │
│  │  6. Compute commission (70%) + "Sin cotizar" ($0) flags          │  │
│  │  7. Diff stage_id/status vs stored row → write DealStageEvent   │  │
│  │  8. Upsert Deal row                                              │  │
│  │  9. Write SyncLog (status, counts, timestamp)                   │  │
│  └────────────────────────────┬─────────────────────────────────--─┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  SQLite (seg.db): Deal, DealStageEvent, SyncLog, Talent,         │  │
│  │  TalentProduct                                                   │  │
│  └────────────────────────────┬─────────────────────────────────--─┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  services/kpis.py + services/funnel.py                          │  │
│  │  - global KPIs, talent ranking (DASH-01)                        │  │
│  │  - per-talent KPIs, funnel, lost opps, brand categories (DASH-02)│ │
│  │  - 6-stage funnel + bottleneck detection (DASH-03)              │  │
│  │  - activity feed from DealStageEvent (DASH-01)                  │  │
│  └────────────────────────────┬─────────────────────────────────--─┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  routers/dashboard.py — GET /dashboard/summary,                 │  │
│  │  /dashboard/talents/{id}, /dashboard/funnel, /dashboard/sync-status│ │
│  └────────────────────────────┬─────────────────────────────────--─┘  │
│                                 │ Bearer JWT (cookie) + JSON            │
│                                 ▼                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  frontend/ (Vanilla JS): Resumen / Por talento / Funnel tabs     │  │
│  │  "Última sync: hace X min" (D-21), warning banner on failure    │  │
│  │  (D-24), "Sincronizando..." toast (D-23)                        │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ONE-TIME SETUP (D-19, separate from sync flow):                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  app/scripts/match_talent_products.py                           │  │
│  │  - GET /api/v2/products (paginate)                               │  │
│  │  - rapidfuzz.process.extractOne(talent.name, product_names,     │  │
│  │    scorer=WRatio, processor=default_process)                    │  │
│  │  - threshold ~85: write talent_products.pipedrive_product_id    │  │
│  │  - below threshold / unmatched products → printed report (D-18) │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
app/
├── integrations/
│   ├── base.py            # shared httpx.Client factory: base_url, x-api-token header, timeout, 429 retry helper
│   └── pipedrive.py        # PipedriveClient: get_deals(), get_deal_products(), get_products(), get_deal_fields(), get_stages()
├── sync/                    # NEW in Phase 2
│   ├── __init__.py
│   ├── scheduler.py         # APScheduler BackgroundScheduler, lifespan-managed
│   └── jobs.py               # sync_pipedrive(db) -> SyncLog
├── services/
│   ├── funnel.py             # NEW: stage aggregation, bottleneck detection, activity feed query
│   └── kpis.py                # NEW: global KPIs, talent ranking, per-talent KPIs, lost-opportunities, brand categories
├── routers/
│   ├── dashboard.py           # NEW: /dashboard/summary, /dashboard/talents/{id}, /dashboard/funnel, /dashboard/sync-status
│   └── sync.py                 # NEW (or merged into dashboard.py): POST /sync/pipedrive (D-22)
├── scripts/
│   └── match_talent_products.py  # NEW: one-time auto-match script (D-16/D-19)
└── models.py                  # ADD: Deal, DealStageEvent, SyncLog tables (+ Alembic migration)
```

### Pattern 1: Pipedrive v2 Client with Header Auth + Cursor Pagination

**What:** A thin `httpx.Client` wrapper with `x-api-token` header (NOT query param), generic cursor-pagination loop, and a cached field/option resolution map.

**When to use:** All Pipedrive v2 calls (`deals`, `dealFields`, `products`, `deals/products`, `stages`).

**Example:**
```python
# app/integrations/pipedrive.py
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
    params.setdefault("limit", 500)  # v2 max
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

**Source:** Auth header requirement confirmed via `[CITED: pipedrive.readme.io/docs/core-api-concepts-authentication]` and `[CITED: pipedrive.readme.io/docs/pipedrive-api-v2-migration-guide]`. Pagination shape (`limit` max 500, `additional_data.next_cursor`) — `[CITED: pipedrive.readme.io/docs/core-api-concepts-pagination]`.

### Pattern 2: Field & Option Resolution Map (v2 shape)

**What:** v2 `custom_fields` is a nested object: `{"custom_fields": {"<hash>": {"value": <raw>}}}`. For enum/set fields, `<raw>` is an integer option `id` (or array of ids for `set`); `dealFields` returns `options: [{id, label}]` per field. Build two maps: `field_key_by_name` (hash lookup) and `option_label_by_field_and_id` (nested dict).

**When to use:** Once per sync run (or cached with short TTL) — required for PIPE-04 (razón de pérdida, categoría de marca, fecha de cobro esperada).

**Example:**
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
        return option_labels[field_key].get(raw)  # enum id -> label
    return raw  # plain value (e.g., date string for "fecha de cobro esperada")
```

**Source:** v2 `custom_fields` nesting and enum `options: [{id, label}]` shape `[CITED: pipedrive.readme.io/docs/pipedrive-api-v2-migration-guide]` + `[CITED: pipedrive community — dealFields option id/label]`. Cross-referenced across two independent sources — MEDIUM-HIGH confidence.

### Pattern 3: Stage-Change Diffing for Activity Feed (DASH-01) + Bottleneck Input (DASH-03)

**What:** A `DealStageEvent` table records `(deal_id, talent_id, from_stage, to_stage, from_status, to_status, detected_at)`. During each sync, before upserting a `Deal`, compare the incoming `stage_id`/`status` to the stored row; if different, insert an event row. The activity feed (DASH-01) queries the most recent N events. Stage-to-stage conversion for bottleneck detection (DASH-03) is computed from **current snapshot counts** (`COUNT(*) WHERE stage_id = X AND status='open'`), not from the event log — the event log only tells you about *transitions seen since this app started syncing*, not full historical flow-through.

**When to use:** This is the recommended approach over polling Pipedrive's `/activities` API or per-deal `/deals/{id}/flow`, because:
- `/deals/{id}/flow` is per-deal only — no bulk/multi-deal endpoint exists `[CITED: Pipedrive developer community — "no endpoint to get updates from multiple deals at once"]`. At 21 talents with ongoing deal volume, N+1 calls per sync is wasteful and risks rate-limit/token budget issues as data grows.
- Pipedrive's `/activities` API tracks user-scheduled activities (calls, meetings, tasks) — not deal stage changes. It is the wrong data source for "deal moved to Cotización" type events.
- Diffing during sync is "free" (data is already being fetched) and gives exactly the granularity needed: "Deal X moved from Llamada → Cotización" events for the activity feed.

**Example schema:**
```python
# app/models.py additions
class Deal(Base):
    __tablename__ = "deals"
    id: Mapped[int] = mapped_column(primary_key=True)
    pipedrive_id: Mapped[int] = mapped_column(unique=True, index=True)
    title: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String, default="MXN")
    stage_id: Mapped[int] = mapped_column(Integer)
    stage_name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # open/won/lost
    talent_id: Mapped[int | None] = mapped_column(ForeignKey("talents.id"), nullable=True)
    commission_amount: Mapped[float] = mapped_column(Float, default=0.0)
    is_sin_cotizar: Mapped[bool] = mapped_column(Boolean, default=False)  # PIPE-03
    loss_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    brand_category: Mapped[str | None] = mapped_column(String, nullable=True)
    expected_collection_date: Mapped[str | None] = mapped_column(String, nullable=True)  # PIPE-04
    update_time: Mapped[str] = mapped_column(String)  # Pipedrive's update_time, for updated_since filter

class DealStageEvent(Base):
    __tablename__ = "deal_stage_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    deal_pipedrive_id: Mapped[int] = mapped_column(Integer, index=True)
    talent_id: Mapped[int | None] = mapped_column(ForeignKey("talents.id"), nullable=True)
    from_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    to_stage: Mapped[str] = mapped_column(String)
    from_status: Mapped[str | None] = mapped_column(String, nullable=True)
    to_status: Mapped[str] = mapped_column(String)
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class SyncLog(Base):
    __tablename__ = "sync_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String, default="pipedrive")
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String)  # running/success/error
    records_synced: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
```

### Pattern 4: Bottleneck Detection (DASH-03) — Concrete Heuristic

**What:** Define the 6 ordered stages (Llamada=1 ... Cobranza=6, mapped via `/stages` `order_nr` per pipeline). For each adjacent pair `(stage_i, stage_i+1)`, compute:

```
conversion_i = count(deals ever reached stage_i+1 or beyond) / count(deals ever reached stage_i)
```

Approximated from current snapshot as:
```
conversion_i ≈ count(deals currently AT stage >= i+1, status IN ('open','won')) 
              / count(deals currently AT stage >= i, status IN ('open','won','lost'))
```

Flag the stage transition with the **lowest** `conversion_i` as the bottleneck, IF the total deal count across all stages exceeds a minimum sample size (e.g., 10) — otherwise return "Datos insuficientes para detectar cuellos de botella" rather than a misleading 0%/100% from tiny samples.

**Rationale:** The mockup's "41% vs 60% industry benchmark" framing requires an external benchmark number that has no data source in this project — `[ASSUMED]` that no such benchmark exists for SEG specifically. The snapshot-ratio approach is self-contained (no external benchmark needed), uses only data already synced, and produces a stable, explainable number ("Solo el X% de los deals en Cotización llegan a Negociación"). This is a Claude's-Discretion recommendation per CONTEXT.md, not a verified industry standard — flagged in Assumptions Log.

**Alternative (also viable, simpler):** "Deals stuck >14 days in current stage" — computable if `Deal` stores `stage_entered_at` (set when `DealStageEvent` diffing detects a stage change, defaulting to `add_time` on first sync). Recommend implementing **both**: the conversion-ratio number for the `.alert.warn` headline, and a count of ">14 days in stage" deals as a secondary metric/list — they answer different questions ("where does the funnel leak" vs. "which specific deals need attention") and both map cleanly to existing mockup elements (`.alert.warn` for the headline, `.deal-row` list for stuck deals).

### Anti-Patterns to Avoid

- **Using `?api_token=` query param on `/api/v2/*` calls:** Silently fails (401) — v2 requires `x-api-token` header. The existing `ARCHITECTURE.md` example code uses the v1 query-param pattern; do not copy it verbatim.
- **Calling `/deals/{id}/flow` per deal for stage history:** No bulk endpoint exists; doing this for all deals on every hourly sync will blow the rate-limit budget as deal volume grows. Use sync-time diffing instead (Pattern 3).
- **Hardcoding enum option IDs for razón de pérdida / categoría de marca:** Option IDs are assigned by Pipedrive when the custom field options were created in THIS Pipedrive account — they are not portable constants. Always resolve via `/dealFields` `options` array at sync time.
- **Computing commission/Sin-cotizar on every dashboard read:** Cheap arithmetic, but storing it on the `Deal` row at sync-write time (Pattern 3 schema) means `services/kpis.py` queries are simple `SUM()`/`COUNT()` aggregates — faster and gives a single source of truth that the activity feed, KPIs, and reports (M5) can all reference identically.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy name matching (D-16 auto-match) | Custom Levenshtein/normalization code | `rapidfuzz.process.extractOne(name, choices, scorer=fuzz.WRatio, processor=utils.default_process)` | Handles accents, punctuation, word-order differences (e.g., "Don Silverio" vs "DON SILVERIO - Producto"); `WRatio` + `default_process` normalizes case/whitespace/punctuation automatically. Hand-rolled string matching will miss edge cases (21 names is small, but errors here mean wrong revenue attribution — high cost of bugs). |
| Hourly scheduled job | `while True: sleep(3600)` thread, or external cron requiring a second container/process | `APScheduler` `BackgroundScheduler` in FastAPI lifespan | APScheduler handles misfire grace, job replacement on restart, and integrates cleanly with `SessionLocal`; a naive sleep-loop thread can't be cleanly stopped/restarted and has no misfire handling. |
| HTTP retry/backoff for Pipedrive 429s | Nothing pre-built recommended — but DO write the ~15-line loop in Pattern 1, don't skip it entirely | Hand-rolled `Retry-After`-aware loop (shown in Pattern 1) | A full `tenacity` dependency is disproportionate for one integration's retry needs at this scale, but skipping retry entirely risks a single transient 429 failing an entire hourly sync (which then shows the D-24 warning banner unnecessarily). |
| Pagination cursor management | Manual `while` loops scattered across each integration call site | Single `_paginate()` generator (Pattern 1) reused for `/deals`, `/dealFields`, `/products`, `/stages` | All v2 list endpoints share the same `cursor`/`next_cursor` shape — one generator function avoids copy-paste pagination bugs (PITFALLS.md Pitfall 6). |

**Key insight:** The deceptively complex problems in this phase are NOT "talk to Pipedrive" (httpx + a thin wrapper suffices, per existing STACK.md) — they are (1) correctly resolving v2's nested+hashed custom fields including enum option IDs, and (2) deriving "activity" and "bottleneck" signals from snapshot data without an API that directly provides them. Both are addressed by the patterns above; neither needs an external library.

## Common Pitfalls

### Pitfall 1: v1-shaped auth code copied from ARCHITECTURE.md's example
**What goes wrong:** `PipedriveClient.__init__` sets `params={"api_token": api_token}` on the `httpx.Client` (as shown in the existing ARCHITECTURE.md Pattern 1 example). Every v2 call returns 401 Unauthorized.
**Why it happens:** ARCHITECTURE.md was researched 2026-06-09 with a v1-shaped example; Pipedrive's v1→v2 auth change (api_token query param → `x-api-token` header) is a recent, easy-to-miss breaking change that doesn't show up unless the v2 auth docs are specifically checked.
**How to avoid:** Use `headers={"x-api-token": settings.PIPEDRIVE_API_TOKEN}` (Pattern 1). Write an integration test that hits `/api/v2/dealFields` (or `/api/v2/users/me`) on startup and asserts a 200, not a 401 — catches this immediately.
**Warning signs:** All Pipedrive calls return HTTP 401 despite a valid token; `params=` dict contains `api_token`.

### Pitfall 2: Enum custom field values treated as final labels instead of option IDs
**What goes wrong:** `custom_fields.<hash>.value` for razón de pérdida / categoría de marca is an **integer** (e.g., `3`), not the string "Presupuesto insuficiente". If the code stores this raw integer as `Deal.loss_reason`, the dashboard shows "3" instead of the label, or the per-reason summary (D-25) groups by integer instead of by the 5 known razones.
**Why it happens:** v1 custom-field pitfall (PITFALLS.md #5) is about hash-key resolution; the v2-specific *second* layer — option-id-to-label resolution for enum/set fields — is easy to miss if the team only addresses "field key resolution" and assumes the returned value is already human-readable.
**How to avoid:** `build_field_maps()` (Pattern 2) must build BOTH the hash→name map AND the per-field `option_id → label` map from `dealFields.options`. Write a test asserting `resolve_custom_field()` returns one of the 5 known razón-de-pérdida strings (or one of the 6 brand categories), not an integer.
**Warning signs:** `Deal.loss_reason` / `Deal.brand_category` columns contain values like `"1"`, `"2"`, `"3"` instead of Spanish text; D-25/D-26 groupings show numeric buckets.

### Pitfall 3: `updated_since` incremental sync misses stage-change events for deals not updated since last sync
**What goes wrong:** If the hourly sync only fetches `updated_since=<last_sync_time>`, deals that haven't changed are skipped — which is correct for the `Deal` table (no change = no update needed), but it means `DealStageEvent` diffing only sees deals Pipedrive reports as updated. This is actually fine for stage-change detection (a stage change updates `update_time`), but **the FIRST sync run has no "previous state" to diff against** — every deal would generate a spurious "stage event" on first sync.
**Why it happens:** The diffing logic (Pattern 3) compares incoming data to the stored `Deal` row; on first sync, no stored row exists, so "from_stage: null → to_stage: X" looks like a transition.
**How to avoid:** Skip `DealStageEvent` creation when `existing_deal is None` (first sync / new deal) — only create events on UPDATE of an existing row, not INSERT. Document this explicitly in the sync job.
**Warning signs:** Activity feed shows dozens of "moved to X" events all timestamped at the moment of the very first sync run.

### Pitfall 4: "Sin talento asignado" deals silently excluded from global totals
**What goes wrong:** D-17 requires deals with unmapped products to be **synced and counted in global totals** under "Sin talento asignado", but NOT counted in per-talent KPIs. If `services/kpis.py`'s global-total query does an INNER JOIN `Deal -> Talent` (to get talent name for display), deals with `talent_id IS NULL` are silently dropped from the global sum — undercounting "Pipeline total" etc.
**Why it happens:** The natural query for "revenue by talent" is `Deal JOIN Talent`, and it's easy to reuse that same query (with a `GROUP BY`) for the global total, which then implicitly filters out `talent_id IS NULL` rows.
**How to avoid:** Global KPI queries must run against `Deal` directly (no join, or LEFT JOIN), while per-talent queries filter `WHERE talent_id = :id`. Add an explicit "Sin talento asignado" row/bucket in the ranking display per D-17, sourced from `WHERE talent_id IS NULL`.
**Warning signs:** Sum of all per-talent revenue ≠ "Pipeline total" KPI; the gap equals the value of unmapped-product deals.

### Pitfall 5: APScheduler job + manual "sync now" running concurrently, double-writing the same Deal rows
**What goes wrong:** If the hourly APScheduler tick fires while a user-triggered "Sincronizar ahora" (D-22/D-23) is still running, both call `sync_pipedrive(db)` concurrently. SQLite's single-writer model (already mitigated by WAL + busy_timeout per Phase 1) reduces lock errors, but two concurrent syncs upserting the same rows can race on `SyncLog` status and waste API budget.
**Why it happens:** D-23 explicitly makes "sync now" async/non-blocking — natural to implement as "just call the same job function in a background thread/task", without considering the scheduler might also fire.
**How to avoid:** Add a simple in-process lock/flag (e.g., a module-level `threading.Lock` or a check on the most recent `SyncLog.status == 'running'` with a staleness timeout) so a second sync request while one is in-flight either no-ops (returns "ya está sincronizando") or queues rather than running in parallel.
**Warning signs:** Two `SyncLog` rows with overlapping `started_at`/`finished_at` ranges; duplicate `DealStageEvent` rows for the same transition.

## Code Examples

### Bulk fetching deal products (v2)
```python
# app/integrations/pipedrive.py
def get_deal_products_bulk(client: httpx.Client, deal_ids: list[int]) -> dict[int, list[dict]]:
    """GET /api/v2/deals/products?deal_ids=1,2,3 — up to 100 deal IDs per call."""
    result: dict[int, list[dict]] = {}
    for chunk_start in range(0, len(deal_ids), 100):
        chunk = deal_ids[chunk_start:chunk_start + 100]
        for item in _paginate(client, "/deals/products", {"deal_ids": ",".join(map(str, chunk))}):
            result.setdefault(item["deal_id"], []).append(item)
    return result
```
**Source:** `[CITED: developers.pipedrive.com changelog — "Introducing new Deal Products bulk operations API", GET /api/v2/deals/products with deal_ids param, up to 100 deal IDs]`

### Incremental sync with `updated_since`
```python
def get_deals(client: httpx.Client, updated_since: str | None = None):
    params = {"status": "all_not_deleted"} if False else {}
    if updated_since:
        params["updated_since"] = updated_since  # RFC3339, e.g. 2026-06-11T10:00:00Z
    yield from _paginate(client, "/deals", params)
```
**Source:** `[CITED: pipedrive v2 GET /deals params — updated_since (RFC3339), filters update_time >= value]`. For the FIRST sync (no prior `SyncLog`), omit `updated_since` to fetch everything — be mindful of the documented 2000-result cap when filtering by `status` (PITFALLS.md Pitfall 6); cursor pagination on the unfiltered `/deals` list endpoint does not carry that 2000 cap (the cap applies specifically to status-filtered searches), but verify deal volume stays well under it at 21-talent scale regardless.

### Talent auto-match script skeleton (D-16/D-18/D-19)
```python
# app/scripts/match_talent_products.py
from rapidfuzz import fuzz, process, utils
from app.database import SessionLocal
from app.models import Talent, TalentProduct
from app.integrations.pipedrive import _client, _paginate

THRESHOLD = 85

def run():
    db = SessionLocal()
    client = _client()
    try:
        products = list(_paginate(client, "/products"))
        product_names = [p["name"] for p in products]

        unmatched_talents = []
        for talent in db.query(Talent).all():
            match = process.extractOne(
                talent.name, product_names, scorer=fuzz.WRatio, processor=utils.default_process
            )
            if match and match[1] >= THRESHOLD:
                name, score, idx = match
                product = products[idx]
                tp = db.query(TalentProduct).filter_by(talent_id=talent.id).first()
                if tp is None:
                    tp = TalentProduct(talent_id=talent.id)
                    db.add(tp)
                tp.pipedrive_product_id = product["id"]
                print(f"MATCHED  {talent.name!r} -> {product['name']!r} (score={score:.1f})")
            else:
                unmatched_talents.append(talent.name)
        db.commit()

        matched_product_ids = {tp.pipedrive_product_id for tp in db.query(TalentProduct).all()}
        unmapped_products = [p["name"] for p in products if p["id"] not in matched_product_ids]

        print("\n--- D-18: Unmapped Pipedrive products (manual review) ---")
        for name in unmapped_products:
            print(f"  - {name}")
        print("\n--- Talents with no match >= threshold (manual review) ---")
        for name in unmatched_talents:
            print(f"  - {name}")
    finally:
        db.close()
```
**Source:** rapidfuzz API `[CITED: github.com/rapidfuzz/RapidFuzz README — process.extractOne(query, choices, scorer=fuzz.WRatio, processor=utils.default_process)]`. Threshold of 85 is `[ASSUMED]` — a reasonable starting point for WRatio (0-100 scale) on short brand/person names, but should be validated against the actual 21 talent names vs. real Pipedrive product catalog during execution (D-18's manual review report is the safety net for any threshold miscalibration).

### APScheduler lifespan integration
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
```python
# app/main.py — add lifespan
from contextlib import asynccontextmanager
from app.sync import scheduler as sync_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_scheduler.start()
    yield
    sync_scheduler.shutdown()

app = FastAPI(title="SEG Talent Intelligence Dashboard", lifespan=lifespan)
```
**Source:** `[CITED: apscheduler.readthedocs.io/en/3.x/userguide.html — BackgroundScheduler.start() returns immediately]`. FastAPI `lifespan` context manager pattern is FastAPI's documented startup/shutdown mechanism `[ASSUMED — standard FastAPI pattern, consistent with training knowledge, not re-verified against FastAPI docs this session since it's unrelated to Pipedrive specifics]`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Pipedrive API v1 (`?api_token=` query param, flat custom fields with `_currency` suffix keys) | Pipedrive API v2 (`x-api-token` header, `custom_fields` nested object) | v2 deals/fields/products moved out of beta March 2025; v1 deprecation grace period ended end of 2025 | All new Pipedrive code in this phase must target v2 — v1 example code in ARCHITECTURE.md (researched 2026-06-09, before this deeper v2 dive) is outdated for auth specifically |
| Per-deal `/deals/{id}/products` (N+1 calls) | Bulk `/api/v2/deals/products?deal_ids=...` (up to 100 per call) | v2 "Deal Products bulk operations API" | Reduces sync API call count roughly Nx for N deals with products — meaningfully reduces token budget consumption at scale |

**Deprecated/outdated:**
- Pipedrive API v1 `api_token` query-param auth: still technically reachable for v1 endpoints during a grace period, but the project should not build new code against it. `[CITED: pipedrive.readme.io — v1 endpoints' "availability and functionality will no longer be guaranteed" past end of 2025]`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Bottleneck detection via stage-to-stage conversion ratio (snapshot-based) is the right heuristic, vs. ">14 days stuck" or an external industry benchmark | Pattern 4 / Common Pitfalls | If the team expects the mockup's literal "41% vs 60% industry benchmark" framing, the conversion-ratio number alone won't match that exact UI copy — may need UI copy adjustment during planning. Low risk: recommended approach is self-consistent and computable; "industry benchmark" framing was itself flagged in CONTEXT.md as undiscussed. |
| A2 | rapidfuzz `WRatio` threshold of 85 is appropriate for matching 21 talent names to Pipedrive product names | Code Examples (auto-match script) | If threshold is too high, some real matches get reported as "unmatched" (extra manual work, but D-18's report catches it — low severity). If too low, a wrong product could be auto-mapped to a talent, causing wrong revenue attribution until D-19's manual correction via `/talents/{id}/products` catches it. Either way the one-time script is reviewable before being trusted, so risk is bounded. |
| A3 | FastAPI `lifespan` context manager (vs. deprecated `@app.on_event("startup")`) is available/preferred in the FastAPI version pinned (`fastapi[standard]>=0.136.3`) | Code Examples (APScheduler integration) | If `lifespan` has any version-specific quirks at 0.136.x, scheduler startup/shutdown wiring may need adjustment — low risk, `lifespan` has been the documented pattern since FastAPI 0.93+, well before the pinned version. |
| A4 | The `/deals` v2 list endpoint (unfiltered, cursor-paginated) does not carry the same 2000-result cap that applies to `status`-filtered searches | Code Examples (incremental sync) | If the cap applies more broadly than documented, a large unfiltered `/deals` fetch on first sync could silently truncate — at 21-talent scale this is unlikely to matter in practice (deal volume far below 2000), but should be spot-checked once real Pipedrive data is accessible during execution. |

## Open Questions

1. **Exact pipeline/stage IDs for the 6 SEG funnel stages (Llamada → Cotización → Negociación → Contrato → En ejecución → Cobranza)**
   - What we know: Pipedrive's `/stages` (or `/pipelines/{id}/stages`) endpoint returns `stage_id`, `name`, `order_nr` per pipeline — this is how `deal.stage_id` maps to a human-readable name and ordering.
   - What's unclear: Whether SEG's Pipedrive account has exactly one pipeline with these 6 stages in this exact order, or whether stage names in Pipedrive differ slightly from PROJECT.md's Spanish labels (e.g., "Llamada" vs "Llamada inicial").
   - Recommendation: First task in implementation should call `/api/v2/stages` (or `/pipelines`) against the real account and log the actual stage names/IDs/order — build the stage-name mapping from real data, not assumed from PROJECT.md alone. This is execution-time discovery, not something resolvable in research without live API access.

2. **Whether `PIPEDRIVE_API_TOKEN` / `PIPEDRIVE_DOMAIN` env vars are already populated with real credentials**
   - What we know: `app/config.py` defines both as optional empty-string defaults (placeholders from Phase 1 per ARCHITECTURE.md build-order guidance).
   - What's unclear: Whether the actual SEG Pipedrive API token/domain are available for integration testing during this phase, or whether early tasks need to be designed to work against mocked/fixture responses until credentials are provided.
   - Recommendation: Planner should include an early task that verifies real credentials are present (or flags a `checkpoint:human-verify` for obtaining them) before building integration tests that hit the live API — PITFALLS.md's recommended "integration test that fetches one real deal and asserts custom fields resolve" (Pitfall 5) depends on this.

3. **"Fecha de cobro esperada" field type — date vs daterange vs text**
   - What we know: PROJECT.md lists it as a custom field; v2 custom field value shapes differ by type (plain string for `date`, possibly `{value, until}` for `daterange`/`timerange` per the dealFields docs' mention of those types).
   - What's unclear: Which Pipedrive field type was actually used when this custom field was configured in the SEG account.
   - Recommendation: Resolve via the same `/dealFields` call that resolves razón de pérdida / categoría de marca — inspect the `field_type` for this field during the stage-1 discovery task (Open Question 1) and branch the parsing accordingly in `resolve_custom_field()`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 + uv | All app code | ✓ | uv 0.11.14 | — |
| PyPI registry access | `uv add apscheduler rapidfuzz` | ✓ (verified live) | apscheduler 3.11.2, rapidfuzz 3.14.5 | — |
| Pipedrive API credentials (`PIPEDRIVE_API_TOKEN`, `PIPEDRIVE_DOMAIN`) | All PIPE-* requirements (live sync, integration tests) | ✗ (placeholders only in `.env`/`config.py`) | — | See Open Question 2 — planner should add a checkpoint to confirm/obtain real credentials, or design early tasks to run against recorded fixture responses (e.g., `respx`-mocked httpx) until credentials are available |
| SQLite (bundled) | `Deal`/`DealStageEvent`/`SyncLog` tables | ✓ | stdlib | — |

**Missing dependencies with no fallback:**
- None — Pipedrive credentials are "missing with fallback" (fixtures/mocks can unblock schema + service-layer development; only the live-sync integration test and auto-match script need real credentials).

**Missing dependencies with fallback:**
- Pipedrive API credentials — develop/test `app/integrations/pipedrive.py` normalization logic against recorded/mocked v2 response shapes (the shapes documented in this research) until real credentials are confirmed available; gate the live "first real sync" task behind a `checkpoint:human-verify` if credentials remain unavailable at execution time.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + httpx-based `TestClient` (FastAPI) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options] testpaths = ["tests"]`) |
| Quick run command | `uv run pytest tests/test_pipedrive_integration.py tests/test_sync.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-01 | Sync paginates and upserts deals; "sync now" endpoint returns 202 and triggers async sync | unit + integration | `uv run pytest tests/test_sync.py -x` | ❌ Wave 0 |
| PIPE-02 | Talent resolution via `talent_products.pipedrive_product_id`; 70% commission computed and stored | unit | `uv run pytest tests/test_kpis.py::test_commission_calculation -x` | ❌ Wave 0 |
| PIPE-03 | `$0` deal classified `is_sin_cotizar=True` | unit | `uv run pytest tests/test_sync.py::test_zero_value_deal_sin_cotizar -x` | ❌ Wave 0 |
| PIPE-04 | Custom fields (loss reason, brand category, expected collection date) resolved from hash+option-id to labels | unit | `uv run pytest tests/test_pipedrive_integration.py::test_resolve_custom_fields -x` | ❌ Wave 0 |
| PIPE-05 | Deal stages mapped to 6 known funnel stage names/order | unit | `uv run pytest tests/test_funnel.py::test_stage_mapping -x` | ❌ Wave 0 |
| DASH-01 | Global KPIs, talent ranking, activity feed endpoints return correct shapes/values from seeded `Deal`/`DealStageEvent` fixtures | integration | `uv run pytest tests/test_dashboard.py::test_summary_endpoint -x` | ❌ Wave 0 |
| DASH-02 | Per-talent KPIs, funnel, lost opportunities (grouped by reason), brand category donut (% by deal count) | integration | `uv run pytest tests/test_dashboard.py::test_talent_detail_endpoint -x` | ❌ Wave 0 |
| DASH-03 | Funnel completo aggregates + bottleneck flag computed from snapshot ratios | unit | `uv run pytest tests/test_funnel.py::test_bottleneck_detection -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_<module>.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipedrive_integration.py` — covers PIPE-04 (field/option resolution), Pitfall 1 (auth header), Pitfall 2 (enum option ids); mock `httpx` responses using recorded v2-shaped JSON (no live credentials assumed by default per Environment Availability)
- [ ] `tests/test_sync.py` — covers PIPE-01/PIPE-02/PIPE-03, Pitfall 3 (first-sync no spurious events), Pitfall 4 (Sin talento asignado in global totals), Pitfall 5 (concurrent sync guard)
- [ ] `tests/test_kpis.py` — covers PIPE-02 commission math, global vs per-talent aggregation (Pitfall 4)
- [ ] `tests/test_funnel.py` — covers PIPE-05 stage mapping, DASH-03 bottleneck heuristic (Pattern 4), activity feed query (DASH-01)
- [ ] `tests/test_dashboard.py` — covers DASH-01/DASH-02 endpoint contracts, D-25/D-26/D-27 (lost opportunities summary + donut by deal count)
- [ ] `tests/conftest.py` additions — fixtures for seeded `Talent`/`TalentProduct`/`Deal`/`DealStageEvent` rows; a `respx`-style or hand-built `httpx.MockTransport` fixture for `PipedriveClient` tests (consider adding `respx` as a dev-only test dependency — evaluate during planning if hand-rolled `MockTransport` proves insufficient)
- [ ] APScheduler install: `uv add apscheduler rapidfuzz` — Wave 0

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (new endpoints reuse Phase 1's `get_current_user` JWT-cookie dependency) | existing `app/auth/dependencies.py` |
| V3 Session Management | no (unchanged from Phase 1) | — |
| V4 Access Control | yes | All new `routers/dashboard.py` and `routers/sync.py` (or equivalent) endpoints MUST include `Depends(get_current_user)` (per-router `dependencies=[...]`, matching `talents.py`'s pattern) — no unauthenticated dashboard data exposure |
| V5 Input Validation | yes | Pydantic schemas for all new response models (`DashboardSummary`, `TalentDetail`, `FunnelOverview`, `SyncStatus`); sync job inputs (cursor, deal IDs) are server-controlled, not user input, but the manual "sync now" endpoint should validate it's idempotent/safe to call repeatedly |
| V6 Cryptography | no | `PIPEDRIVE_API_TOKEN` is a server-side secret loaded via `pydantic-settings` (existing `.env` pattern) — no new crypto needed |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Pipedrive API token leaked via logs/error messages during sync job error handling | Information Disclosure | `SyncLog.error_message` should capture exception `str()` but the `PipedriveClient`/httpx setup must never log full request objects (which would include the `x-api-token` header) — use `httpx`'s default logging level (no request/response body logging) and avoid `print(response.request.headers)`-style debugging left in committed code |
| Unauthenticated access to new `/dashboard/*` and `/sync/*` endpoints exposing revenue data | Access Control / Information Disclosure | `dependencies=[Depends(get_current_user)]` on the new routers, identical to `app/routers/talents.py`'s existing pattern — verify with a test asserting 401 without a valid session cookie |
| Manual "sync now" endpoint triggers unbounded/duplicate Pipedrive API calls if spammed (no rate limiting on the trigger itself) | Denial of Service (of own token budget) | Pitfall 5's concurrency guard (in-process lock / `SyncLog.status == 'running'` check) doubles as basic abuse protection — a second "sync now" click while one is in-flight is a no-op, not a new API burst |

## Sources

### Primary (HIGH confidence)
- [Pipedrive Authentication docs](https://pipedrive.readme.io/docs/core-api-concepts-authentication) — confirmed `x-api-token` header required for `/api/v2/*` example calls
- [Pipedrive API v2 Migration Guide](https://pipedrive.readme.io/docs/pipedrive-api-v2-migration-guide) — `custom_fields` nesting shape, v1→v2 field/ID renames, `dealFields` `field_code`
- [Pipedrive Pagination docs](https://pipedrive.readme.io/docs/core-api-concepts-pagination) — cursor-based pagination, `limit` max 500, `additional_data.next_cursor`
- [Pipedrive Deals v1/v2 reference](https://developers.pipedrive.com/docs/api/v1/Deals) — deal object fields, `updated_since`, `status` 2000-result cap, `filter_id`
- [Pipedrive "Introducing new Deal Products bulk operations API" changelog](https://developers.pipedrive.com/changelog/post/introducing-new-deal-products-bulk-operations-api) — `GET /api/v2/deals/products?deal_ids=...` up to 100 IDs
- PyPI JSON API (live, 2026-06-11) — `apscheduler==3.11.2`, `rapidfuzz==3.14.5`, source repos confirmed
- [APScheduler 3.x User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) — `BackgroundScheduler.start()` non-blocking behavior
- [RapidFuzz GitHub README](https://github.com/rapidfuzz/RapidFuzz) — `process.extractOne(query, choices, scorer=fuzz.WRatio, processor=utils.default_process)`

### Secondary (MEDIUM confidence)
- Pipedrive Developer Community thread on `dealFields` `options: [{id, label}]` for enum/set fields — consistent with official v2 migration guide's described `custom_fields` shape
- Pipedrive Developer Community threads on `/deals/{id}/flow` being per-deal only, no bulk stage-history endpoint
- [Pipedrive Token-Based Rate Limits changelog](https://developers.pipedrive.com/changelog/post/breaking-changes-token-based-rate-limits-for-api-requests) — 30,000 base tokens/day × plan multiplier × seats, rolled out through end of 2025

### Tertiary (LOW confidence)
- WebSearch on httpx retry patterns (tenacity vs hand-rolled) — general 2026 community consensus, used to justify NOT adding tenacity rather than as a hard technical fact
- Bottleneck detection heuristic (Pattern 4) — original research synthesis, not sourced from any external "Pipedrive bottleneck best practice" doc (none found); flagged in Assumptions Log A1

## Metadata

**Confidence breakdown:**
- Standard stack (apscheduler, rapidfuzz): HIGH — verified live against PyPI, well-known maintained GitHub repos, slopcheck `[OK]`
- Pipedrive v2 API shape (auth header, pagination, custom fields, bulk products): MEDIUM-HIGH — official docs + cross-referenced community sources agree, but official docs pages are JS-rendered and some details (exact `/dealFields` JSON example) came via WebSearch summaries rather than direct doc rendering
- Architecture (sync layer, activity feed, bottleneck detection): MEDIUM — sync/scheduler pattern matches existing ARCHITECTURE.md and is well-established; activity feed and bottleneck heuristics are research-derived recommendations (Claude's Discretion items from CONTEXT.md), not externally verified "best practices" — flagged as such
- Pitfalls: HIGH for Pitfalls 1-2 (directly verified against official v2 auth/custom-field docs, and Pitfall 1 directly corrects existing project research); MEDIUM for Pitfalls 3-5 (logical consequences of the recommended architecture, not externally documented incidents)

**Research date:** 2026-06-11
**Valid until:** 30 days (Pipedrive API is actively evolving — v2 endpoints continue to move out of beta; re-verify auth/pagination shapes if implementation is delayed beyond ~30 days). apscheduler/rapidfuzz versions are stable libraries — re-verification of those specifically is lower priority.
