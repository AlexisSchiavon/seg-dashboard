---
plan: 02-01
phase: 02-pipedrive-integration-core-dashboard
status: complete
completed_at: 2026-06-14
commits:
  - af9907e
  - 5adbced
  - 6862dd1
  - eaab460
self_check: PASSED
---

## What Was Built

Full Pipedrive sync vertical slice: v2 client, sync job, hourly scheduler, "Sincronizar ahora" button + "Última sync" indicator, talent↔product auto-match script. Verified live against real SEG Pipedrive account — 476 deals synced across 4 real pipeline stages.

## Tasks Completed

| Task | Status | Commit | Notes |
|------|--------|--------|-------|
| Task 1: Models, migration, deps, test scaffolding | ✓ | af9907e | Deal/DealStageEvent/SyncLog models; apscheduler/rapidfuzz added; 31 tests scaffolded |
| Task 2: Pipedrive v2 client + sync job | ✓ | 5adbced | x-api-token header, cursor pagination, commission/Sin-cotizar/event-diffing/concurrency guard |
| Task 3: Sync endpoint, scheduler, dashboard shell | ✓ | 6862dd1 | /sync/pipedrive POST (202), /sync/status GET, hourly APScheduler, index.html + dashboard.js + styles.css |
| Task 4: Live data verification checkpoint | ✓ | eaab460 | 476 deals synced; talent renaming + manual overrides; v2 field shape fix; 31/31 tests pass |

## Key Files Created

- `app/models.py` — Deal, DealStageEvent, SyncLog ORM models (SQLAlchemy 2.0 Mapped/mapped_column)
- `app/integrations/pipedrive.py` — v2 client with x-api-token, cursor pagination, 429 backoff, build_field_maps (field_name/field_code shape)
- `app/sync/jobs.py` — sync_pipedrive(db) with concurrency guard, commission 70%, is_sin_cotizar, event diffing; PIPE-05 stage split documented
- `app/sync/scheduler.py` — APScheduler BackgroundScheduler, hourly sync job
- `app/routers/sync.py` — POST /sync/pipedrive (async 202), GET /sync/status; auth-protected
- `app/scripts/match_talent_products.py` — rapidfuzz auto-match + MANUAL_PRODUCT_MATCHES + NO_PRODUCT_TALENTS
- `app/scripts/seed_talents.py` — 21 talents with exact Pipedrive product name alignment
- `frontend/index.html` — dashboard shell: nav, tabbar (Resumen/Por talento/Funnel), live-pill, Sincronizar ahora button
- `frontend/js/dashboard.js` — setPage, loadSyncStatus, triggerSync, showToast
- `frontend/css/styles.css` — nav, tabbar, live-pill, kpi-grid, card, btn components; .card padding 16px, .kpi-val weight 500
- `tests/test_pipedrive_integration.py` + `tests/test_sync.py` — 31 tests, all passing

## Decisions Made

- **PIPE-05 (blocking anti-pattern):** Pipedrive pipeline 2 has only 4 stages (IDs 6=Llamada, 7=Cotización, 8=Negociación, 9=Contrato y factura). "En ejecución" and "Cobranza" are Trello-sourced (Phase 4). funnel.py in Wave 2 must use 4 real counts + 2 placeholder empty buckets.
- **v2 field shape:** build_field_maps uses `field_name`/`field_code` (not `name`/`key` from v1). Mocks in conftest.py updated to match. Critical: confirm v2 shape before mocking any future Pipedrive endpoints.
- **Talent mapping:** 8 talent names renamed to match exact Pipedrive product names. Don Silverio + Don Wicho share one product (MANUAL_PRODUCT_MATCHES). Dulce/Tony Franco/Casandra Salinas have no Pipedrive product (NO_PRODUCT_TALENTS) — synced with talent_id=NULL per D-17.
- **Admin creds:** Admin user seeded as `santillan@talentagency.mx` / `ChangeMe123!` (idempotent via seed_admin.py). This email must match .env ADMIN_EMAIL.
- **Alembic:** Live seg.db upgraded to head (c35f623eaa21). Run `alembic current` vs `alembic heads` before any live-verify checkpoint.

## Live Verification Results

- 476 deals synced from live Pipedrive (all read-only GET calls)
- Stage distribution: Llamada=127, Cotización=94, Negociación=133, Contrato=122 → sums to 476 (zero dropped)
- commission_amount = value × 0.70 for all non-zero deals
- is_sin_cotizar=True for $0 deals
- loss_reason / brand_category stored as resolved Spanish labels (not integers)
- 31/31 tests pass

## Self-Check

- [x] All 4 tasks executed and committed
- [x] 31/31 tests pass (`uv run pytest -x -q`)
- [x] App boots: `from app.main import app` succeeds with scheduler lifespan
- [x] /sync/pipedrive auth-protected (401 without cookie, 202 with)
- [x] Live Pipedrive sync verified: 476 deals in 4 real stages, labels correct, commission correct
- [x] PIPE-05 anti-pattern documented in code (jobs.py comment) and this summary
