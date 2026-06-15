# Phase 04: Trello Integration & Collection Automation — Research

**Researched:** 2026-06-14
**Domain:** Trello REST API, SQLAlchemy model extension, revenue projection math, dashboard endpoint extension
**Confidence:** HIGH — all Trello board data verified via live API; all codebase patterns confirmed via source reads

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Trello Board Structure (TRELLO-01)**
- D-39: One board for all talents. `TRELLO_BOARD_IDS` env var already has the board ID — `69312a9d5523703a1ce1a413` (verified live).
- D-40: List-to-state mapping (VERIFIED via live API):
  - `"Contrato"`, `"Firmar contrato (todos)"`, `"Enviar factura"` → **ejecucion**
  - `"Cobrar"`, `"Enviar encuesta"` → **cobranza**
  - `"Finalizados"` → **cerrado**
  - `"Otros pendientes"` → **Ignorar** (not synced)
- D-41: Sync only cards from the lists above. All others ignored.

**Deal ↔ Trello Card Linkage (TRELLO-02)**
- D-42: Primary match: card name ≈ Pipedrive deal title (fuzzy/brand-prefix match).
- D-43: Automation-created cards store Pipedrive deal ID as a Trello custom field. **CRITICAL: Custom Fields Power-Up is DISABLED on the board and the workspace is on a free plan (products: []). Custom fields cannot be created via API. Alternative: store Pipedrive deal ID in the card description header (structured first line).** Researcher has flagged this — see Section "Critical Finding: Custom Fields Not Available".
- D-44: Collection date location — RESOLVED. See Section "Collection Date Finding".

**Automation Trigger (TRELLO-03)**
- D-45: Polling-based automation. The sync job detects `status == "won"` deals with no linked Trello card and creates one. Reconciliation: each sync run checks by title match (or description deal ID) before creating.
- D-46: New Trello card created in `"Contrato"` list (list ID: `69312ac640ae158381706ff8`) — confirmed as the correct entry list.

**Revenue Projection Logic (DASH-02)**
- D-47: Three-layer projection using `venta_total` (full deal value, not 70% commission):
  - **Cobrado** (green): cards in `"Finalizados"` list
  - **Proyección** (blue): cards in `"Contrato"` / `"Firmar contrato (todos)"` / `"Enviar factura"` (ejecucion state)
  - **Pendiente** (amber): cards in `"Cobrar"` / `"Enviar encuesta"` (cobranza state)
- D-48: Date grouping — RESOLVED. See Section "Collection Date Finding".
- D-49: 4-month window: 1 prior month + current month + 2 future months (sliding).
- D-50: Endpoint returns `income_projection: [{month, cobrado, proyeccion, pendiente}]` and `payment_calendar: [{month, amount}]`.

**Frontend Integration (DASH-02 — already built)**
- D-51: Frontend `renderIncomeProjection`, `renderPaymentCalendar` already implemented in `dashboard.js`. Backend adds fields to `/dashboard/talents/{id}` response.
- D-52: Extend existing `/dashboard/talents/{id}` endpoint (add new fields to `TalentDetail` schema), not a new sub-endpoint.

**Sync Pattern (carry-forward)**
- D-20: Hourly auto-sync + manual button — Trello sync hooks into `app/sync/jobs.py` and `app/sync/scheduler.py` `_run_all_syncs()`.
- D-22: Same toast/banner UX for Trello sync errors.

### Claude's Discretion

- Talent attribution for Trello cards: falls through to linked Pipedrive deal's talent. If no match, card goes to "Sin talento asignado" bucket.
- Duplicate card guard: if a deal already has a linked card (by description deal ID or title match), automation skips creation.
- `"Enviar encuesta"` list inclusion: counts toward collection amounts in the "pendiente" projection layer (same as "Cobrar"). Implementation detail left to planner.

### Deferred Ideas (OUT OF SCOPE)

- Webhook-based real-time sync (Pipedrive webhooks)
- `Categoria_Detectada` cross-source linking (Sheets ↔ Trello)
- Per-talent Trello board
- "Enviar encuesta" as confirmed Cobrado state
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRELLO-01 | Sync Trello cards for deals with signed contracts, distinguishing "en ejecución" vs "en cobranza" | Board lists verified via live API; list IDs and state mapping documented in Standard Stack section |
| TRELLO-02 | Trello cards display expected collection dates | Collection date analysis complete — Trello due date has <10% coverage; Pipedrive `expected_collection_date` has 0% coverage on live data. Solution: extract month from card name/description or fall back to current month. Documented in Critical Findings. |
| TRELLO-03 | When a Pipedrive deal is marked "ganado", system creates a Trello card with the expected collection date | POST /cards API verified; custom fields unavailable (free plan) — deal ID stored in description header instead. Reconciliation pattern documented. |
| DASH-02 | Por talento — monthly revenue projection (cobrado/proyección/pendiente stacked bars), collection calendar, top 3 campaigns, full campaign table | Frontend render functions already implemented; backend data shape documented; math algorithm specified. |
</phase_requirements>

---

## Summary

Phase 4 adds the Trello integration layer that completes the "Por talento" tab. The work splits into four streams: (1) a new `TrelloCard` SQLAlchemy model + Alembic migration, (2) a `trello.py` httpx wrapper following the existing `pipedrive.py` pattern, (3) a `sync_trello()` job function in `jobs.py` that syncs cards and creates missing ones for won deals, and (4) extending `/dashboard/talents/{id}` to return `income_projection` + `payment_calendar` + individual deal lists.

Two critical real-world findings from live API inspection shape the plan. First, the Trello workspace is on a **free plan** with Custom Fields Power-Up disabled — the API returns "Custom Fields Power-Up disabled for board" when attempting to create custom fields. The D-43 plan to store Pipedrive deal IDs as Trello custom fields is not executable as specified. The fallback is storing the deal ID as a structured first line in the card description (e.g., `pipedrive_deal_id: 123`). Second, the **Trello due date field has near-zero coverage** (≤10% across all lists, 0% on the main execution lists). Pipedrive's `expected_collection_date` field also has **0% data coverage** across all 476 deals in the live database. The collection date for the payment calendar must be derived from the card name/description month hints or defaulted to the deal's `add_time` month as a proxy.

The name-matching analysis shows 3 exact matches, 12 partial (brand-prefix) matches, and 9 no-matches out of a 24-card sample — confirming that fuzzy/prefix matching on the first segment before ` - ` or ` x ` is the right strategy.

**Primary recommendation:** Implement the `trello.py` wrapper + `TrelloCard` model + `sync_trello()` job + endpoint extension as 4 sequential waves. Use description-header storage for the deal ID link. Use the `add_time` month from the linked Pipedrive deal as the collection date fallback when no due date exists on the card.

---

## Critical Findings (VERIFIED via live API)

### Board Structure — Confirmed [VERIFIED: live Trello API]

Board ID: `69312a9d5523703a1ce1a413` (board name: "Admin TA")

| List Name | List ID | State | Card Count |
|-----------|---------|-------|------------|
| Contrato | `69312ac640ae158381706ff8` | ejecucion | 9 |
| Firmar contrato (todos) | `69312acb534b0e80508bf4e5` | ejecucion | 2 |
| Enviar factura | `69312ad08fe346b82da12e1d` | ejecucion | 8 |
| Cobrar | `69312ad63829ef3ac9967d1a` | cobranza | 24 |
| Enviar encuesta | `69312adeac51905b84f53c35` | cobranza | 31 |
| Otros pendientes | `6996256c42ccdae7f69e4814` | IGNORAR | 28 |
| Finalizados | `69d8336e46709e935f4307fe` | cerrado | 26 |

List names in D-40 match **exactly**. List IDs must be stored as a constant map in `trello.py` (hardcoded from env + this mapping), not discovered dynamically on every sync run (the list names are stable; discovery adds an extra API call per sync with no benefit).

### Custom Fields Not Available — Plan Change Required [VERIFIED: live Trello API]

Calling `POST /api/v1/customFields` returns `"Custom Fields Power-Up disabled for board"`. The Trello workspace is on the free plan (`products: []` confirmed). Custom fields are a paid feature in Trello.

**D-43 as written is not executable.** The alternative that preserves bidirectional linkage without custom fields:

Store the Pipedrive deal ID as the **first line of the card description** using a parseable marker:
```
[seg:deal_id=12345]
```
This line is written when `sync_trello()` creates a new card. On subsequent syncs, the integration reads `card.desc` and extracts the deal ID from this marker (regex: `\[seg:deal_id=(\d+)\]`). This enables precise reconciliation identical to the custom field approach, without any paid feature.

The planner must note this change from D-43 in the plan file.

### Collection Date Finding — Low Coverage [VERIFIED: live Trello API + local DB]

| Source | Coverage |
|--------|----------|
| Trello `due` field — ejecucion lists (Contrato/Firmar/Enviar factura) | 0/19 cards have due dates |
| Trello `due` field — Cobrar list | 1/24 cards have a due date |
| Trello `due` field — Enviar encuesta list | 6/31 cards have due dates |
| Trello `due` field — Finalizados list | 2/26 cards have due dates |
| Pipedrive `expected_collection_date` — all deals | 0/476 deals have this field populated |

**Decision for D-48:** Neither source has adequate coverage. The planner must implement a fallback chain:
1. Use Trello card `due` date if present (ISO 8601, e.g. `2026-04-17T18:00:00.000Z`)
2. If no due date, extract month from card description text patterns (e.g. "pago en Julio", "pago en el mes de ejecución", "30 días naturales posteriores a la...")
3. If description parsing fails, use the linked Pipedrive deal's `add_time` month + 2 months as a proxy (approximate collection lag)
4. If no Pipedrive link, use `synced_at` month

The `payment_calendar` will always have 4 months of data (the sliding window), but amounts for months with no concrete date evidence will be estimated. The frontend already handles this gracefully — it renders whatever data the backend sends.

The description month extraction is **best-effort, not required for MVP**. The planner may scope this as a Wave 0 or Wave 1 task depending on complexity. Storing `collection_date` as nullable on the model is mandatory; the projection math groups by month and a null date falls back to step 3 above.

### Name Matching Analysis [VERIFIED: live API + local DB comparison]

Sample of 24 Trello card names vs 476 Pipedrive deal titles:
- **3 exact matches** (case-insensitive)
- **12 partial matches** on brand prefix (segment before ` - ` or ` x `)
- **9 no-matches** (card name contains talent shorthand not in deal title, or deal title has variant spelling)

The fuzzy match algorithm:
1. Normalize both sides: lowercase, strip extra spaces, remove accents using `unicodedata.normalize('NFKD')`.
2. Extract brand prefix: split card name on ` - ` or ` x `, take first segment as the brand key.
3. Check if any deal title contains the brand key (substring match after normalization).
4. If multiple matches, pick the one with the highest `SequenceMatcher` ratio (stdlib `difflib`).
5. Threshold: only accept matches with ratio ≥ 0.70.

This is the same pattern as D-16 for talent name matching in Phase 2.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Trello card sync (read) | API / Backend (jobs.py) | Database (TrelloCard model) | Background job, not triggered by UI — same pattern as Pipedrive/Sheets sync |
| Trello card creation (write) | API / Backend (jobs.py) | External (Trello API) | Only write operation to external system; must be idempotent (reconciliation guard) |
| Deal↔card linkage | API / Backend (trello_service.py) | Database (deal_id FK) | Business logic: fuzzy match + description-header parse; not a DB constraint |
| Revenue projection math | API / Backend (trello_service.py) | Database (TrelloCard + Deal queries) | Deterministic math in Python per CLAUDE.md; frontend only renders the result |
| Income projection / payment calendar render | Browser / Client (dashboard.js) | — | Already implemented: `renderIncomeProjection()`, `renderPaymentCalendar()` — backend wires data |
| Top 3 campaigns + campaign table render | Browser / Client (dashboard.js) | — | Already implemented: `renderTopCampaigns()`, `renderCampaignTable()` — needs new data shape from backend |
| Sync schedule | API / Backend (scheduler.py) | — | APScheduler, same hourly job as Pipedrive/Sheets |

---

## Standard Stack

### Core (no new packages — all already installed)

| Library | Version | Purpose | Confirmed |
|---------|---------|---------|-----------|
| httpx | 0.28.x | Trello API calls (same as Pipedrive) | [VERIFIED: already in .venv] |
| SQLAlchemy | 2.0.x | TrelloCard model (same declarative style) | [VERIFIED: already in use] |
| Alembic | 1.18.x | New migration for trello_cards table | [VERIFIED: already in use] |
| difflib (stdlib) | bundled | Fuzzy name matching (SequenceMatcher) | [VERIFIED: Python stdlib] |
| unicodedata (stdlib) | bundled | Accent normalization for name matching | [VERIFIED: Python stdlib] |
| re (stdlib) | bundled | Description header parsing (deal ID extraction) | [VERIFIED: Python stdlib] |

**No new pip packages required.** Phase 4 reuses the entire existing stack.

### Package Legitimacy Audit

No new packages to install. This section is not applicable — Phase 4 installs zero new dependencies.

---

## Architecture Patterns

### System Architecture Diagram

```
[APScheduler hourly / Manual "Sincronizar ahora"]
          |
          v
  sync_trello(db)  ← app/sync/jobs.py
          |
    ┌─────┴──────────────────────────┐
    │                                │
    v                                v
[GET /boards/{id}/lists/{list_id}/cards]    [Won deals in DB with no trello_card]
    via trello.py httpx wrapper              (status="won", deal_id FK = null on TrelloCard)
    |                                        |
    v                                        v
 Upsert TrelloCard rows              POST /1/cards → new card in "Contrato" list
 by trello_card_id (natural key)     store [seg:deal_id=N] in card.desc
 link to Deal via fuzzy title match  then upsert TrelloCard row for new card
    |
    v
 trello_service.income_projection(db, talent_id)
    → query TrelloCard JOIN Deal WHERE talent_id = X
    → group by (list_state, month) using collection_date fallback chain
    → return {income_projection: [...], payment_calendar: [...]}
    |
    v
 GET /dashboard/talents/{id}  ← extended to call trello_service
    → TalentDetail (extended schema)
    → income_projection, payment_calendar, individual deals list
    |
    v
 Browser: renderIncomeProjection() / renderPaymentCalendar()
          renderTopCampaigns(deals) / renderCampaignTable(deals, lostOpps)
          (all render functions already exist — just need real data)
```

### Recommended Project Structure (additions only)

```
app/
├── integrations/
│   └── trello.py           ← NEW: httpx wrapper (get_board_lists, get_list_cards, create_card)
├── services/
│   └── trello_service.py   ← NEW: income_projection(), payment_calendar() math
├── sync/
│   └── jobs.py             ← EXTEND: add sync_trello(db) function
│       └── scheduler.py    ← EXTEND: add sync_trello to _run_all_syncs()
├── models.py               ← EXTEND: add TrelloCard model
├── schemas/
│   └── dashboard.py        ← EXTEND: add MonthProjection, CalendarEntry, DealRow, extend TalentDetail
└── routers/
    └── dashboard.py        ← EXTEND: call trello_service in get_talent_detail()
alembic/versions/
└── XXXX_add_trello_cards_table.py  ← NEW: migration
tests/
└── test_trello.py          ← NEW: unit tests for trello_service math + integration wrapper
```

### Pattern 1: TrelloCard SQLAlchemy Model [VERIFIED: matches existing models.py style]

```python
# app/models.py — add after Lead class
from sqlalchemy import Date

class TrelloCard(Base):
    __tablename__ = "trello_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    trello_card_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    list_id: Mapped[str] = mapped_column(String)       # Trello list ID
    list_name: Mapped[str] = mapped_column(String)     # e.g. "Cobrar"
    list_state: Mapped[str] = mapped_column(String)    # ejecucion | cobranza | cerrado
    # FK to Deal (nullable — card may not match any deal yet)
    deal_id: Mapped[int | None] = mapped_column(
        ForeignKey("deals.id"), nullable=True, index=True
    )
    # Pipedrive deal ID extracted from description header [seg:deal_id=N]
    pipedrive_deal_id_desc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Collection date — from Trello due field or fallback chain
    collection_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

Note: `deal_id` is a FK to `deals.id` (the local PK), not `deals.pipedrive_id`. The service layer resolves Pipedrive deal ID → local `deals.id` before setting this FK.

### Pattern 2: trello.py httpx Wrapper [VERIFIED: mirrors pipedrive.py structure]

```python
# app/integrations/trello.py
import httpx
from app.config import settings
from app.integrations.base import get_with_retry

BASE_URL = "https://api.trello.com/1"

# Hardcoded list-ID → state mapping (verified 2026-06-14 via live API)
LIST_STATE_MAP: dict[str, str] = {
    "69312ac640ae158381706ff8": "ejecucion",   # Contrato
    "69312acb534b0e80508bf4e5": "ejecucion",   # Firmar contrato (todos)
    "69312ad08fe346b82da12e1d": "ejecucion",   # Enviar factura
    "69312ad63829ef3ac9967d1a": "cobranza",    # Cobrar
    "69312adeac51905b84f53c35": "cobranza",    # Enviar encuesta
    "69d8336e46709e935f4307fe": "cerrado",     # Finalizados
    # "6996256c42ccdae7f69e4814" → Otros pendientes (NOT in map = ignored)
}

def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=30.0)

def _auth_params() -> dict:
    return {"key": settings.TRELLO_API_KEY, "token": settings.TRELLO_TOKEN}

def get_list_cards(client: httpx.Client, list_id: str) -> list[dict]:
    """GET /lists/{listId}/cards — returns all cards with id, name, due, desc."""
    params = {**_auth_params(), "fields": "id,name,due,desc"}
    resp = get_with_retry(client, f"/lists/{list_id}/cards", params)
    return resp.json()

def create_card(
    client: httpx.Client,
    list_id: str,
    name: str,
    desc: str = "",
    due: str | None = None,
) -> dict:
    """POST /cards — creates a new card. Returns the created card dict."""
    params = {**_auth_params(), "idList": list_id, "name": name}
    if desc:
        params["desc"] = desc
    if due:
        params["due"] = due  # ISO 8601 string
    resp = client.post("/cards", params=params)
    resp.raise_for_status()
    return resp.json()
```

**Auth pattern:** `?key=…&token=…` query params on every request — confirmed via live API. No Bearer header, no OAuth. [VERIFIED: live API calls]

### Pattern 3: sync_trello() in jobs.py [VERIFIED: mirrors sync_sheets() pattern]

```python
def sync_trello(db: Session) -> SyncLog:
    # 1. Concurrency guard — filter by source="trello" (same per-source pattern as sheets)
    running = (
        db.query(SyncLog)
        .filter(SyncLog.source == "trello", SyncLog.status == "running")
        .order_by(SyncLog.started_at.desc())
        .first()
    )
    if running is not None and not _is_stale(running):
        return running

    # 2. Write SyncLog(source="trello")
    # 3. For each list_id in LIST_STATE_MAP:
    #      cards = trello.get_list_cards(client, list_id)
    #      for card in cards:
    #        deal_id = _extract_deal_id_from_desc(card["desc"])  # [seg:deal_id=N]
    #        if not deal_id:
    #          deal_id = _fuzzy_match_deal(card["name"], db)  # returns deals.id or None
    #        collection_date = _parse_collection_date(card)
    #        upsert TrelloCard by trello_card_id
    # 4. Detect won deals missing a TrelloCard → create card + upsert
    # 5. SyncLog success/error
```

The per-source concurrency guard (`source == "trello"`) is **mandatory** — learned from Phase 3 code review (CR-03): without source filter, a running Pipedrive sync blocks Trello sync.

### Pattern 4: Revenue Projection Math [VERIFIED: logic matches D-47]

```python
# app/services/trello_service.py
from datetime import date, timedelta
from calendar import month_abbr

def _month_label(d: date) -> str:
    """Returns e.g. 'Jun 2026'"""
    return f"{month_abbr[d.month]} {d.year}"

def _sliding_window_months(anchor: date) -> list[date]:
    """Returns [anchor-1month, anchor, anchor+1month, anchor+2months] as first-of-month dates."""
    months = []
    for delta in [-1, 0, 1, 2]:
        y, m = divmod(anchor.month - 1 + delta, 12)
        months.append(date(anchor.year + y, m + 1, 1))
    return months

def income_projection(db: Session, talent_id: int) -> list[dict]:
    """
    Returns [{month: "Jun 2026", cobrado: N, proyeccion: N, pendiente: N}]
    for the 4-month sliding window (D-49).
    Uses venta_total (Deal.value, not commission_amount) per D-47.
    Groups by TrelloCard.collection_date month; falls back to Deal.add_time month
    when collection_date is null.
    """
    window = _sliding_window_months(date.today())
    result = {_month_label(m): {"cobrado": 0.0, "proyeccion": 0.0, "pendiente": 0.0} for m in window}
    window_labels = set(result.keys())

    # Query: TrelloCard JOIN Deal for this talent
    rows = (
        db.query(TrelloCard, Deal)
        .join(Deal, TrelloCard.deal_id == Deal.id)
        .filter(Deal.talent_id == talent_id)
        .all()
    )
    for card, deal in rows:
        # Resolve month
        col_date = card.collection_date
        if col_date is None and deal.add_time:
            # Fallback: add_time month + 2 as proxy
            try:
                base = date.fromisoformat(deal.add_time[:10])
                y, m = divmod(base.month - 1 + 2, 12)
                col_date = date(base.year + y, m + 1, 1)
            except (ValueError, TypeError):
                col_date = date.today()
        if col_date is None:
            col_date = date.today()

        label = _month_label(col_date.replace(day=1))
        if label not in window_labels:
            continue  # outside 4-month window

        amount = deal.value or 0.0
        if card.list_state == "cerrado":
            result[label]["cobrado"] += amount
        elif card.list_state == "ejecucion":
            result[label]["proyeccion"] += amount
        elif card.list_state == "cobranza":
            result[label]["pendiente"] += amount

    return [{"month": k, **v} for k, m_date in zip(result.keys(), window) for v in [result[k]]]
```

### Pattern 5: Extended TalentDetail Schema [VERIFIED: matches dashboard.py consumer]

```python
# app/schemas/dashboard.py — additions

class MonthProjection(BaseModel):
    month: str          # "Jun 2026" — matches renderIncomeProjection() expectation
    cobrado: float
    proyeccion: float
    pendiente: float

class CalendarEntry(BaseModel):
    month: str          # "Jun 2026" — matches renderPaymentCalendar() expectation
    amount: float

class DealRow(BaseModel):
    title: str
    amount: float
    list_state: str     # ejecucion | cobranza | cerrado | perdido (for .sbadge CSS class)
    trello_card_id: str | None = None

class TalentDetail(BaseModel):
    # ... existing fields ...
    income_projection: list[MonthProjection] | None = None   # None = shows placeholder
    payment_calendar: list[CalendarEntry] | None = None       # None = shows placeholder
    deals: list[DealRow] | None = None                       # for renderTopCampaigns + renderCampaignTable
```

### Pattern 6: loadTalentDetail Frontend Change [VERIFIED: lines 976-979 of dashboard.js]

Current code (line 976-979):
```javascript
const activeStages = (data.funnel || []).filter((s) => s.count > 0);
renderTopCampaigns(activeStages);
renderCampaignTable(activeStages, data.lost_opportunities);
```

Phase 4 change — replace those 3 lines with:
```javascript
// Phase 4: use individual deals from TrelloCard data instead of stage aggregates
const activeDeals = data.deals || [];
renderTopCampaigns(activeDeals);  // renderTopCampaigns must be updated to accept deals
renderCampaignTable(activeDeals, data.lost_opportunities);
```

`renderTopCampaigns` and `renderCampaignTable` currently expect `{stage, count, amount}` shape. Per UI-SPEC D-51: these two functions must be updated to accept `{title, amount, list_state}` shape (individual deal objects). This is a **frontend JS change** required in Phase 4.

### Anti-Patterns to Avoid

- **Dynamic list discovery per sync:** Don't call `GET /boards/{id}/lists` on every sync run. The list ID → state mapping is a constant. One extra API call per hourly sync with no benefit.
- **Using Trello custom fields:** Disabled on free plan. Any code path calling `POST /customFields` or `GET /cards?customFieldItems=true` will silently return empty results or error.
- **Blocking concurrency guard without source filter:** `SyncLog.status == "running"` without `SyncLog.source == "trello"` would block Trello sync when Pipedrive is running. **Learned from Phase 3 CR-03.**
- **Storing deal FK as `pipedrive_id` (integer):** The `deal_id` FK must point to `deals.id` (local PK), not `deals.pipedrive_id`. This is consistent with how `DealStageEvent.deal_pipedrive_id` is stored as an integer but lookups join on `Deal.pipedrive_id` — keep the FK to the PK for referential integrity.
- **Re-fetching all 100 cards on incremental sync:** Trello has no `updated_since` filter on `GET /lists/{id}/cards`. Always fetch all cards per list (small volume: max 31 cards per list, 100 total across 6 lists). No cursor pagination needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string matching | Custom Levenshtein | `difflib.SequenceMatcher` (stdlib) | Already in Python stdlib; covers brand-prefix matching adequately for 100-card volume |
| HTTP retry/backoff for Trello | New retry decorator | `base.get_with_retry()` (already in `app/integrations/base.py`) | Exact same 429-aware retry exists; Trello returns 429 with Retry-After header |
| Date arithmetic for 4-month window | Custom month iteration | `calendar` + date arithmetic (stdlib) | No third-party library needed for month arithmetic at this scale |
| Accent normalization | Custom char table | `unicodedata.normalize('NFKD', s).encode('ascii', 'ignore')` (stdlib) | Handles ñ, á, é, etc. for name matching |

**Key insight:** Zero new dependencies are needed. This phase is pure business logic layered on the existing stack.

---

## Common Pitfalls

### Pitfall 1: Duplicate Card Creation on Retry
**What goes wrong:** If `sync_trello()` creates a Trello card for a won deal, then the DB commit fails (network error, etc.), the next sync run will try to create the card again — resulting in duplicate Trello cards.
**Why it happens:** The card creation (external write) and the DB upsert are not atomic.
**How to avoid:** Write the `TrelloCard` row to DB (with `trello_card_id` from the API response) BEFORE the `db.commit()`. If the commit fails, the next sync run won't find a TrelloCard row and will try again — but the Trello card already exists. Guard: before creating, also check Trello API for existing cards with matching description `[seg:deal_id=N]`. In practice for this scale (a few dozen won deals), the simpler guard is: check TrelloCard table for `pipedrive_deal_id_desc == deal.pipedrive_id` before calling POST.
**Warning signs:** Multiple Trello cards with identical names in the "Contrato" list.

### Pitfall 2: Trello Rate Limits
**What goes wrong:** Trello's rate limit is 300 requests per 10 seconds per token. Syncing 6 lists × 1 GET request = 6 requests. Creating cards adds 1 POST per won deal (typically 0-2 new won deals per sync cycle). Total: ~8-10 requests per sync. This is far below the limit.
**Why it happens:** Not a real risk at current data volumes. Documented as a known constraint for when the board grows.
**How to avoid:** The existing `get_with_retry()` handles 429 responses with `Retry-After` backoff. No changes needed.

### Pitfall 3: Month Label Format Mismatch
**What goes wrong:** `renderIncomeProjection()` and `renderPaymentCalendar()` expect `month: "Jun 2026"` (abbreviated English month name + full year). If the backend sends `"2026-06"` or `"Junio 2026"`, the frontend renders correctly but the text labels will look wrong.
**Why it happens:** Python's `calendar.month_abbr` returns English abbreviations ("Jan", "Feb", ..., "Dec"). The frontend uses `escHtml(item.month)` — it renders whatever string it receives.
**How to avoid:** Use `calendar.month_abbr[d.month]` (English 3-letter abbreviation) in `_month_label()`. The UI-SPEC specifies `"Jun 2026"` format explicitly (from `renderIncomeProjection` source).

### Pitfall 4: TalentDetail Schema Extension Breaking Existing Clients
**What goes wrong:** Adding `income_projection`, `payment_calendar`, `deals` fields to `TalentDetail` must use `| None = None` defaults. If required, the existing tests that build `TalentDetail` without these fields will fail.
**Why it happens:** Pydantic v2 with required fields breaks existing test fixtures.
**How to avoid:** All three new fields must be `Optional` with `None` defaults. The frontend already handles null: `data.income_projection || null` renders the placeholder.

### Pitfall 5: The `sync_pipedrive` Concurrency Bug — Already Fixed
**What goes wrong:** The Phase 2 code review (obs #846) found that `sync_pipedrive` lacks a `source` filter on the concurrency guard — it blocks on ANY running sync, including sheets. This was fixed in Phase 3.
**Why it happens:** Known issue, confirmed fixed.
**How to avoid:** In `sync_trello`, always use `SyncLog.source == "trello"` in the concurrency guard query.

### Pitfall 6: Card Names with Unicode Accents in Title Matching
**What goes wrong:** Trello card "Mariana Sánchez" doesn't match Pipedrive deal "Mariana Sanchez" because the accent differs.
**Why it happens:** The live data has inconsistent accent usage (confirmed: "Havoline - Mama mecanic" vs "Havoline México - Mama mecanic", "Hana Sushi x Mariana Sanchez" vs "Hana Sushi - Mariana Sánchez").
**How to avoid:** Normalize both sides with `unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').lower()` before comparison.

---

## Code Examples

### Description Header: Writing Deal ID when Creating Card
```python
# Source: D-43 fallback (custom fields not available on free plan)
def _make_card_desc(pipedrive_deal_id: int, extra_desc: str = "") -> str:
    header = f"[seg:deal_id={pipedrive_deal_id}]"
    if extra_desc:
        return f"{header}\n\n{extra_desc}"
    return header

# When creating:
desc = _make_card_desc(deal.pipedrive_id)
new_card = trello.create_card(client, list_id="69312ac640ae158381706ff8", name=deal.title, desc=desc)
```

### Description Header: Parsing Deal ID on Sync
```python
import re

_DEAL_ID_RE = re.compile(r'\[seg:deal_id=(\d+)\]')

def _extract_deal_id_from_desc(desc: str | None) -> int | None:
    if not desc:
        return None
    m = _DEAL_ID_RE.search(desc)
    return int(m.group(1)) if m else None
```

### Fuzzy Name Matching
```python
import unicodedata
from difflib import SequenceMatcher

def _normalize(s: str) -> str:
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    return s.lower().strip()

def _brand_prefix(card_name: str) -> str:
    """Extract brand prefix before ' - ' or ' x '."""
    for sep in [" - ", " x "]:
        if sep in card_name:
            return _normalize(card_name.split(sep)[0])
    return _normalize(card_name)

def fuzzy_match_deal(card_name: str, deals: list[Deal]) -> Deal | None:
    """Match card name to best Pipedrive deal. Returns None if no match >= 0.70."""
    prefix = _brand_prefix(card_name)
    card_norm = _normalize(card_name)
    best_deal = None
    best_ratio = 0.0
    for deal in deals:
        deal_norm = _normalize(deal.title)
        # Substring check on prefix first (fast path)
        if prefix and prefix in deal_norm:
            ratio = SequenceMatcher(None, card_norm, deal_norm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_deal = deal
    if best_ratio >= 0.70:
        return best_deal
    return None
```

### Alembic Migration Pattern
```python
# alembic/versions/XXXX_add_trello_cards_table.py
# Source: mirrors c35f623eaa21_add_deals_deal_stage_events_sync_logs.py pattern
def upgrade() -> None:
    op.create_table(
        "trello_cards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trello_card_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("list_id", sa.String(), nullable=False),
        sa.Column("list_name", sa.String(), nullable=False),
        sa.Column("list_state", sa.String(), nullable=False),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deals.id"), nullable=True),
        sa.Column("pipedrive_deal_id_desc", sa.Integer(), nullable=True),
        sa.Column("collection_date", sa.Date(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trello_cards_trello_card_id", "trello_cards", ["trello_card_id"], unique=True)
    op.create_index("ix_trello_cards_deal_id", "trello_cards", ["deal_id"])

def downgrade() -> None:
    op.drop_index("ix_trello_cards_deal_id", "trello_cards")
    op.drop_index("ix_trello_cards_trello_card_id", "trello_cards")
    op.drop_table("trello_cards")
```

---

## Runtime State Inventory

> Phase 4 is NOT a rename/refactor phase — this section covers only the external state the sync job modifies.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Local SQLite `seg.db` — no `trello_cards` table yet | Alembic migration `add_trello_cards_table` |
| Live service config | Trello board "Admin TA" (id: `69312a9d5523703a1ce1a413`) — 100 cards across 6 lists | Read-only for sync; write for card creation (new won deals only) |
| OS-registered state | None | — |
| Secrets/env vars | `TRELLO_API_KEY`, `TRELLO_TOKEN`, `TRELLO_BOARD_IDS` — all present in `.env` [VERIFIED]; `TRELLO_WORKSPACE_NAME`, `TRELLO_ORG_ID` also in `.env` but not needed by integration | None — credentials ready |
| Build artifacts | None | — |

**Custom fields NOT available:** Confirmed free-plan restriction. No migration or setup needed for custom fields — use description header approach instead.

---

## State of the Art

| Old Approach (in dashboard.js) | Phase 4 Approach | Impact |
|-------------------------------|------------------|--------|
| `renderTopCampaigns(stages)` receives stage aggregates `{stage, count, amount}` | Receives individual deal objects `{title, amount, list_state}` | Campaigns show real names and Trello status, not just stage totals |
| `renderCampaignTable(stages, lostOpps)` receives stage aggregates | Receives individual deal objects | Same — individual deal rows with sbadge status |
| `data.income_projection \|\| null` → placeholder shown | Real data: `[{month, cobrado, proyeccion, pendiente}]` | Stacked bar chart activates |
| `data.payment_calendar \|\| null` → placeholder shown | Real data: `[{month, amount}]` | Timeline nodes render with real amounts |
| `TalentDetail` schema: no projection fields | Extended: `income_projection`, `payment_calendar`, `deals` added (all optional) | Backward-compatible extension |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Trello list names are stable (won't be renamed by the SEG team) | Standard Stack — LIST_STATE_MAP | List state mapping breaks silently; sync would skip renamed lists. Mitigation: store list IDs (stable UUIDs) not names in the constant map. [Already mitigated — map uses IDs, not names] |
| A2 | The fuzzy match threshold of 0.70 produces acceptable matches for the full card set | Pattern 3 | False positives (wrong deal linked to card) could corrupt projection amounts. Mitigation: the description header `[seg:deal_id=N]` takes precedence over fuzzy match for automation-created cards. |
| A3 | `add_time` month + 2 months is a reasonable collection lag proxy for cards without a due date | Critical Findings / collection date fallback | Projection amounts appear in wrong month. Low financial impact at this stage — projection is approximate by design. |
| A4 | The Trello free plan restriction on custom fields is permanent for this board | Critical Findings | If the team upgrades Trello plan, custom fields become available and D-43 as originally specified could be implemented. The description-header approach remains compatible — it's additive. |

---

## Open Questions

1. **Should "Enviar encuesta" cards count toward "pendiente" amounts?**
   - What we know: D-40 maps "Enviar encuesta" → cobranza state, and "pendiente" uses the cobranza layer (D-47). So yes by current spec.
   - What's unclear: "Enviar encuesta" has 31 cards (the largest list), including cards that may be effectively "cobrado" (survey sent = collection confirmed for that team). Including them inflates "pendiente".
   - Recommendation: Include in "pendiente" per D-47. If the team disagrees post-Phase 4, the list_state mapping is a one-line config change.

2. **What amount to use for Trello cards with no Pipedrive match?**
   - What we know: 9/24 sampled cards had no deal match. These cards have deal amounts embedded in descriptions (e.g., "$300k mas iva", "$160k + IVA") but parsing free-text MXN amounts is fragile.
   - What's unclear: Whether unmatched cards should contribute to revenue projection at all.
   - Recommendation: Unmatched cards (deal_id = null) contribute amount = 0 to projection. They are still synced and visible in the DB. The planner may add a Wave 2 task to parse description amounts if needed.

3. **Should `loadTalentDetail` update use `data.deals` or keep the current `data.funnel` path as fallback?**
   - What we know: Lines 976-979 of dashboard.js currently use `data.funnel`. Phase 4 must change this to `data.deals`.
   - What's unclear: Whether to keep the old `data.funnel` path as a fallback when `data.deals` is null.
   - Recommendation: Use `data.deals || []` — if empty, `renderTopCampaigns([])` and `renderCampaignTable([], ...)` both show their existing empty-state messages. No funnel fallback needed.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Runtime | ✓ | 3.12.x | — |
| httpx | Trello API calls | ✓ | 0.28.x (in .venv) | — |
| SQLAlchemy | TrelloCard model | ✓ | 2.0.x (in .venv) | — |
| Alembic | Migration | ✓ | 1.18.x (in .venv) | — |
| Trello API | Sync + card creation | ✓ | REST v1 | — |
| `TRELLO_API_KEY` | Auth | ✓ | Present in .env | — |
| `TRELLO_TOKEN` | Auth | ✓ | Present in .env | — |
| `TRELLO_BOARD_IDS` | Board ID | ✓ | `69312a9d5523703a1ce1a413` in .env | — |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (confirmed active, 111 tests collected) |
| Config file | none — discovery via `pytest.ini` / `pyproject.toml` defaults |
| Quick run command | `python3 -m pytest tests/test_trello.py -x -q` |
| Full suite command | `python3 -m pytest -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TRELLO-01 | `sync_trello()` upserts cards from all 6 relevant lists | unit | `pytest tests/test_trello.py::test_sync_trello_upserts_cards -x` | ❌ Wave 0 |
| TRELLO-01 | Cards in "Otros pendientes" are NOT synced | unit | `pytest tests/test_trello.py::test_sync_trello_ignores_otros_pendientes -x` | ❌ Wave 0 |
| TRELLO-01 | `list_state` is correctly assigned from list ID | unit | `pytest tests/test_trello.py::test_list_state_mapping -x` | ❌ Wave 0 |
| TRELLO-02 | `collection_date` is set from Trello due date when present | unit | `pytest tests/test_trello.py::test_collection_date_from_due -x` | ❌ Wave 0 |
| TRELLO-02 | `collection_date` falls back to `add_time + 2 months` when no due date | unit | `pytest tests/test_trello.py::test_collection_date_fallback -x` | ❌ Wave 0 |
| TRELLO-03 | Won deals with no TrelloCard get a card created | unit | `pytest tests/test_trello.py::test_auto_create_card_for_won_deal -x` | ❌ Wave 0 |
| TRELLO-03 | Won deals with existing TrelloCard are NOT duplicated | unit | `pytest tests/test_trello.py::test_no_duplicate_card_creation -x` | ❌ Wave 0 |
| TRELLO-03 | Description header `[seg:deal_id=N]` is written on card creation | unit | `pytest tests/test_trello.py::test_card_desc_contains_deal_id -x` | ❌ Wave 0 |
| DASH-02 | `income_projection` returns 4 months with correct cobrado/proyeccion/pendiente | unit | `pytest tests/test_trello.py::test_income_projection_math -x` | ❌ Wave 0 |
| DASH-02 | `/dashboard/talents/{id}` response includes `income_projection` field | integration | `pytest tests/test_dashboard.py::test_talent_detail_includes_income_projection -x` | ❌ Wave 0 |
| DASH-02 | Concurrency guard uses `source="trello"` filter | unit | `pytest tests/test_trello.py::test_sync_trello_concurrency_guard -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_trello.py -x -q`
- **Per wave merge:** `python3 -m pytest -x -q` (full 111+ suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_trello.py` — covers all TRELLO-01/02/03 and DASH-02 requirements
- [ ] `TrelloCard` model and migration must exist before tests can run

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | JWT auth inherited from router `dependencies=[Depends(get_current_user)]` — no new auth surface |
| V3 Session Management | No | No new session endpoints |
| V4 Access Control | Yes | All new dashboard endpoints protected by existing `get_current_user` dependency |
| V5 Input Validation | Yes | `response_model=TalentDetail` validates output; Trello card `desc` is read-only for parsing, never echoed back raw |
| V6 Cryptography | No | No new crypto |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Trello API token leakage in logs | Information Disclosure | `str(exc)` only in SyncLog.error_message (same rule as T-02-01 / T-03-01 for Pipedrive/Sheets); never log `repr(response.request)` |
| Description header injection via card name | Tampering | The `[seg:deal_id=N]` pattern is regex-parsed with `\d+` — only numeric values accepted; non-numeric values are ignored |
| XSS via Trello card name in frontend | Tampering | All API-sourced strings use `escHtml()` — this is the existing convention (CR-02) and must be applied to `deal.title` in new render paths |

---

## Sources

### Primary (HIGH confidence)
- Live Trello REST API — board lists, card data, custom fields availability confirmed 2026-06-14
- `app/integrations/pipedrive.py`, `app/integrations/base.py` — httpx wrapper pattern (source read)
- `app/sync/jobs.py` — sync_pipedrive/sync_sheets patterns (source read)
- `app/sync/scheduler.py` — APScheduler setup (source read)
- `app/models.py` — SQLAlchemy 2.0 model style (source read)
- `app/schemas/dashboard.py` — Pydantic schema conventions (source read)
- `app/routers/dashboard.py` — endpoint extension point (source read)
- `frontend/js/dashboard.js` lines 757-979 — render function signatures confirmed (source read)
- `seg.db` live database — deal titles, expected_collection_date coverage (0%), deal counts

### Secondary (MEDIUM confidence)
- Trello REST API official docs `https://developer.atlassian.com/cloud/trello/rest/` — POST /cards parameters, auth pattern (confirmed via live API behavior)

### Tertiary (LOW confidence — none)

---

## Metadata

**Confidence breakdown:**
- Board structure / list IDs: HIGH — verified via live API, exact list names match D-40 spec
- Custom fields: HIGH — API returns definitive error "Custom Fields Power-Up disabled for board"
- Collection date coverage: HIGH — counted from live API response (all 100 cards checked)
- Name matching algorithm: MEDIUM — tested on 24-card sample; full board has ~100 cards
- Revenue projection math: HIGH — logic derived directly from D-47/D-49/D-50 spec + frontend source code
- Frontend render contract: HIGH — read from dashboard.js source, confirmed data shapes

**Research date:** 2026-06-14
**Valid until:** 2026-07-14 (stable API; only update if Trello plan changes or board is restructured)
