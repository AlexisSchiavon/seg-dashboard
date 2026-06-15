---
phase: 04-trello-integration-collection-automation
reviewed: 2026-06-14T23:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - alembic/versions/ee55974a0232_add_trello_cards_table.py
  - app/integrations/trello.py
  - app/models.py
  - app/routers/dashboard.py
  - app/routers/sync.py
  - app/schemas/dashboard.py
  - app/services/trello_service.py
  - app/sync/jobs.py
  - app/sync/scheduler.py
  - frontend/js/dashboard.js
  - tests/conftest.py
  - tests/test_dashboard.py
  - tests/test_trello.py
findings:
  critical: 2
  warning: 4
  info: 2
  total: 8
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-06-14T23:00:00Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Phase 4 adds Trello card syncing, deal linkage, reconciliation (auto-create cards
for won deals), income projection math, payment calendar, and a frontend rewire
from funnel-stage aggregates to per-deal rows. The overall architecture is sound:
source-isolated concurrency guards, idempotent upserts, a clean two-step desc-then-
fuzzy-match strategy, and XSS defenses on all user-sourced strings.

Two blockers require attention before this ships. First, `sync_pipedrive` still
carries a cross-source concurrency guard (no `source=` filter), meaning a running
Trello or Sheets sync silently no-ops Pipedrive. This was flagged in Phase 3 review
and remains unresolved. Second, the Trello `httpx.Client` is never closed in `sync_trello` —
each sync run leaks a connection pool that is never cleaned up, which will accumulate
over the hourly scheduler runs.

Four warnings cover: dead `renderTalentDeals` function in the frontend; an
unguarded `KeyError` on `response["id"]` during reconciliation that can silence
card-creation failures; `resolve_deal_id` doing an unbounded full-table scan on
every card during sync; and the `sync.py` router concurrency guard checking all
sources instead of filtering by source.

---

## Critical Issues

### CR-01: `sync_pipedrive` concurrency guard missing source filter — blocks all syncs when Trello/Sheets runs

**File:** `app/sync/jobs.py:49-55`

**Issue:** `sync_pipedrive`'s guard queries `SyncLog.status == "running"` with no
`source=` filter. After Phase 4, the scheduler runs `sync_pipedrive → sync_sheets
→ sync_trello` in sequence, each writing its own `SyncLog(source=...)`. If any
sync is in-flight (e.g. Trello), the next scheduled hourly call to `sync_pipedrive`
sees the running Trello log and no-ops, returning it unchanged. The function is
documented to guard against itself, not against other sources. `sync_sheets` and
`sync_trello` both correctly filter by `source=`; `sync_pipedrive` does not.

The bug pre-dates Phase 4 but becomes a reliability defect only now that three
sources run sequentially and Trello can be slow (fetching from 6 lists + card
creation calls).

**Fix:**
```python
# app/sync/jobs.py — sync_pipedrive concurrency guard, line 49
running = (
    db.query(SyncLog)
    .filter(SyncLog.source == "pipedrive", SyncLog.status == "running")  # add source filter
    .order_by(SyncLog.started_at.desc())
    .first()
)
```

---

### CR-02: `httpx.Client` leaked in `sync_trello` — connection pool never closed

**File:** `app/sync/jobs.py:348`

**Issue:** `client = trello._client()` constructs a new `httpx.Client` (which owns
a connection pool) but the client is never closed and never used as a context
manager. The `try/except` block does not include a `finally: client.close()`.
Every invocation of `sync_trello` — scheduled hourly — leaks one connection pool.
Over 24 hours that is 24 leaked pools. `httpx` does log a `ResourceWarning` but
does not auto-close on GC in CPython in all configurations.

`sync_pipedrive` has the same pattern with `pipedrive._client()` (pre-existing),
but the Trello client is new in Phase 4 and should not inherit the same defect.

**Fix:**
```python
# app/sync/jobs.py — sync_trello, replace bare client construction
with trello._client() as client:
    # ... all existing code from line 354 to 450 moves inside this block
    pass
```

Alternatively, make `_client()` return a context manager directly:
```python
# app/integrations/trello.py
from contextlib import contextmanager

@contextmanager
def _client():
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
        yield c
```

Note: the test helper `mock_client()` in test_trello.py does not call `.close()`
either, but that only affects test processes which tear down immediately.

---

## Warnings

### WR-01: `renderTalentDeals` is dead code — never called, conflicts with `renderCampaignTable`

**File:** `frontend/js/dashboard.js:571-601`

**Issue:** `renderTalentDeals` (lines 571-601) renders deal rows into `#talent-deals`
using old Pipedrive deal field names (`deal.is_sin_cotizar`, `deal.stage_name`,
`deal.value`). These fields do not exist on the Phase 4 `DealRow` schema
(`{title, amount, list_state, trello_card_id}`). The function is never called
anywhere in the file — `loadTalentDetail` (line 1033-1034) calls only
`renderTopCampaigns` and `renderCampaignTable`.

`renderCampaignTable` (line 902) also writes to `#talent-deals` using the correct
Phase 4 field names. The orphaned `renderTalentDeals` will silently produce broken
HTML if ever called (undefined properties render as empty strings in template
literals but `deal.value` in `formatMXN` returns `"$0"` rather than crashing).

**Fix:** Remove `renderTalentDeals` entirely (lines 568-601). If the function's
visual format is ever needed again it should be rebuilt against `DealRow` fields.

---

### WR-02: Unguarded `response["id"]` KeyError during reconciliation can swallow card-creation failures

**File:** `app/sync/jobs.py:435`

**Issue:** After `trello.create_card(...)` returns, the code does:
```python
new_card = TrelloCard(trello_card_id=response["id"], ...)
```
`create_card` calls `resp.raise_for_status()`, so HTTP errors surface as
`httpx.HTTPStatusError` and are caught by the outer `except Exception`. However,
the Trello API on success may theoretically return a 200 with a body that omits
`"id"` (e.g. rate-limit or partial responses), or the mock returns
`TRELLO_CREATED_CARD` which has `"id": "card-new-001"`. A missing `"id"` key
raises an unhandled `KeyError` that propagates to the outer `except`, marks the
entire sync as `"error"`, and **rolls back all card upserts from the read phase**
(lines 354-393 were already committed at line 395, but the reconciliation block
adds new `TrelloCard` objects not yet committed). The rollback at line 460 covers
only the uncommitted additions; the read-phase commit is safe. The real risk is
that a single bad reconciliation response corrupts the sync log status for all
sources.

**Fix:**
```python
card_id = response.get("id")
if not card_id:
    # Log the anomaly and skip this deal rather than failing the whole sync
    continue  # or raise ValueError(f"Trello create_card returned no id for deal {won_deal.pipedrive_id}")
new_card = TrelloCard(trello_card_id=card_id, ...)
```

---

### WR-03: `resolve_deal_id` full-table scan on `Deal` for every card — O(cards × deals) per sync

**File:** `app/services/trello_service.py:322`

**Issue:** The fuzzy-match fallback in `resolve_deal_id` executes
`db.query(Deal).all()` on every card that lacks a `[seg:deal_id=N]` header.
In `sync_trello`, this is called inside a nested loop (once per card per list).
With 476 Pipedrive deals and ~20 Trello cards without desc headers, this is
~20 full-table-scans of the deals table per sync run.

More critically, the preloaded `all_deals` list at line 351 (`all_deals = db.query(Deal).all()`)
is **not passed** to `resolve_deal_id` — the function re-queries the database
independently. The preloaded list is only used for the `linked_deal` lookup after
`resolve_deal_id` returns. The intent to avoid N+1 queries (comment at line 350)
is not achieved for the fuzzy-match path.

**Fix:** Pass the preloaded deals list into `resolve_deal_id` instead of re-querying:
```python
# trello_service.py
def resolve_deal_id(
    db: Session,
    card_desc: str | None,
    card_name: str,
    all_deals: list[Deal] | None = None,  # new param
) -> int | None:
    pipedrive_id = _extract_deal_id_from_desc(card_desc)
    if pipedrive_id is not None:
        deal = db.query(Deal).filter(Deal.pipedrive_id == pipedrive_id).first()
        if deal is not None:
            return deal.id

    candidates = all_deals if all_deals is not None else db.query(Deal).all()
    matched = fuzzy_match_deal(card_name, candidates)
    return matched.id if matched is not None else None

# jobs.py sync_trello call site
deal_id = trello_service.resolve_deal_id(db, card_desc, card_name, all_deals=all_deals)
```

---

### WR-04: `/sync/pipedrive` router concurrency guard is source-agnostic — can block manual triggers incorrectly

**File:** `app/routers/sync.py:33`

**Issue:** The manual sync endpoint checks:
```python
db.query(SyncLog).filter(SyncLog.status == "running").order_by(...).first()
```
This returns any running `SyncLog` regardless of source. If the hourly scheduler
starts a Trello sync, a user clicking "Sincronizar ahora" will receive
`{"status": "already_running"}` even though no Pipedrive sync is actually in
progress. The user then sees the toast "Ya hay una sincronización en curso" and
the Pipedrive data is not refreshed.

The router docstring says "A failure in one sync does not prevent the others from
completing" but the concurrency guard contradicts this intent for the manual trigger.

**Fix:**
```python
# app/routers/sync.py:33
running = (
    db.query(SyncLog)
    .filter(SyncLog.source == "pipedrive", SyncLog.status == "running")
    .order_by(SyncLog.started_at.desc())
    .first()
)
```

---

## Info

### IN-01: `TrelloCard.synced_at` has no corresponding column-level index despite being a frequently used temporal marker

**File:** `alembic/versions/ee55974a0232_add_trello_cards_table.py:34` / `app/models.py:147`

**Issue:** `synced_at` uses `server_default` and `onupdate` (ORM-level, not
`server_onupdate`) making it a natural candidate for queries filtering "cards
updated since last sync." No index exists. At current scale (~50 cards) this is
negligible, but it is inconsistent with `deal_id` (indexed) and `trello_card_id`
(indexed). If a future incremental sync filters by `synced_at`, a full scan occurs.

**Fix:** Add to migration and model if incremental Trello sync is planned:
```python
# In migration upgrade():
op.create_index('ix_trello_cards_synced_at', 'trello_cards', ['synced_at'], unique=False)
```

---

### IN-02: `test_talent_detail_includes_income_projection` fixture dependency order is fragile

**File:** `tests/test_dashboard.py:328`

**Issue:** The test signature is `(auth_client, db_session, seed_trello_cards, seed_deals)`.
`seed_trello_cards` depends on `seed_deals` (declared in conftest), so both
fixtures insert rows. However, listing `seed_deals` explicitly in the test
signature means pytest instantiates it **twice** — once as a dependency of
`seed_trello_cards` and once as a direct argument — but since pytest deduplicates
fixtures by name within the same test, this is safe in practice. The redundancy
is confusing and could cause ordering issues if fixture scopes are ever changed.

The test also accesses `seed_deals` to get `talent_a_id` via `seed_deals["deal_open"]`
rather than `seed_trello_cards`, even though `seed_trello_cards` already has the
linked deal objects available.

**Fix:** Remove `seed_deals` from the direct test parameters; access it via
`seed_trello_cards["card_ejecucion"].deal_id` or reconstruct the talent_id from
the `seed_trello_cards` return dict if needed:
```python
def test_talent_detail_includes_income_projection(auth_client, db_session, seed_trello_cards):
    talent_a_id = seed_trello_cards["card_ejecucion"].deal.talent_id  # via relationship
    # or: query db_session for talent_a_id from the card's deal_id
```

---

_Reviewed: 2026-06-14T23:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
