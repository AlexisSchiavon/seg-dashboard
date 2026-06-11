---
phase: 01-foundation-auth-talent-catalog-health-check
plan: 02
subsystem: api
tags: [fastapi, sqlalchemy, pydantic, talent-catalog, crud, seed-script]

requires:
  - phase: 01-01
    provides: "Talent/TalentProduct SQLAlchemy models, get_db, get_current_user cookie guard, auth_client/client test fixtures, app.main FastAPI app"
provides:
  - "Protected /talents CRUD router (list, create, patch) with response_model= Pydantic schemas"
  - "/talents/{id}/products CRUD (list, add, delete) for normalized Pipedrive product mapping (TAL-02)"
  - "app/schemas/talent.py: TalentCreate, TalentUpdate, TalentRead, TalentProductCreate, TalentProductRead"
  - "app/scripts/seed_talents.py: idempotent 21-talent seed (TALENT_NAMES), runnable via python -m app.scripts.seed_talents"
  - "5 new talent integration tests (test_talents.py), full suite green (12/12)"
affects: [01-03, phase-02-pipedrive-sync]

tech-stack:
  added: []
  patterns:
    - "Router-level dependencies=[Depends(get_current_user)] to protect all routes in one place"
    - "PATCH endpoints use payload.model_dump(exclude_unset=True) to update only provided fields"
    - "Idempotent seed scripts accept an optional session_factory param for test-DB targeting"
    - "response_model= Pydantic schemas only — never return raw ORM objects (Anti-Pattern 4)"

key-files:
  created:
    - app/schemas/talent.py
    - app/routers/talents.py
    - app/scripts/seed_talents.py
    - tests/test_talents.py
  modified:
    - app/main.py

key-decisions:
  - "seed_talents() takes an optional session_factory=SessionLocal parameter so tests/test_talents.py can target the conftest TestSessionLocal without a separate code path"

patterns-established:
  - "Router-level auth guard: APIRouter(dependencies=[Depends(get_current_user)]) protects every route in the file without per-handler repetition"
  - "DELETE /talents/{id}/products/{product_id} verifies product.talent_id == talent_id before deleting (cross-talent tamper guard, T-02-05)"

requirements-completed: [TAL-01, TAL-02]

duration: ~25min
completed: 2026-06-11
---

# Phase 01 Plan 02: Talent Catalog CRUD + Seed Summary

**Protected `/talents` CRUD + `/talents/{id}/products` Pipedrive-mapping endpoints, backed by Pydantic response schemas, with an idempotent 21-talent seed script and 5 green integration tests.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-11T19:09:00Z
- **Completed:** 2026-06-11T19:35:00Z
- **Tasks:** 2/2 completed
- **Files modified:** 5 (1 new schema, 1 new router, 1 new seed script, 1 new test file, 1 modified main.py)

## Accomplishments
- Authenticated users can list, create, and PATCH talents via `/talents` with no code changes required to add new talents (TAL-01)
- One or more Pipedrive product IDs can be attached to and listed/removed per talent via `/talents/{id}/products` (TAL-02), stored in the normalized `talent_products` table
- All `/talents` routes reject unauthenticated requests with 401 (router-level guard, T-02-01)
- The 21 real SEG talents seed into the DB idempotently via `python -m app.scripts.seed_talents` — verified end-to-end (21 after first run, 21 after second run)
- Full test suite green: 12/12 (7 from Plan 01 + 5 new talent tests)

## Task Commits

1. **Task 1: Talent + product schemas and protected CRUD router (TDD)** - `a3731e5` (test, RED) -> `5771090` (feat, GREEN)
2. **Task 2: Idempotent 21-talent seed and seeded-presence test** - `b68cf49` (feat)

_Note: Task 1 followed RED/GREEN TDD — failing tests committed first, then the router/schema implementation that makes them pass._

## Files Created/Modified
- `app/schemas/talent.py` - TalentBase/TalentCreate/TalentUpdate/TalentRead, TalentProductCreate/TalentProductRead, all read schemas with `from_attributes=True`
- `app/routers/talents.py` - `APIRouter(prefix="/talents", dependencies=[Depends(get_current_user)])`; GET/POST `/talents`, PATCH `/talents/{id}`, GET/POST `/talents/{id}/products`, DELETE `/talents/{id}/products/{product_id}`
- `app/scripts/seed_talents.py` - `TALENT_NAMES` (21 entries), `seed_talents(session_factory=SessionLocal)` idempotent insert, `__main__` guard
- `tests/test_talents.py` - test_talents_require_auth, test_create_talent, test_update_talent, test_add_talent_product, test_seeded_talents_present
- `app/main.py` - added `from app.routers import talents` + `app.include_router(talents.router)` before the StaticFiles mount

## Decisions Made
- `seed_talents()` accepts an optional `session_factory` parameter (defaults to `SessionLocal`) so `test_seeded_talents_present` can seed against the test DB's `TestSessionLocal` without duplicating seed logic.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None. `python -m app.scripts.seed_talents` requires `alembic upgrade head` to have been run first (the `talents` table must exist) — this is the same precondition as `seed_admin.py` from Plan 01 and is not a regression; verified manually against a fresh SQLite DB (migrate -> seed twice -> 21 talents both times).

## User Setup Required
None for this plan - no new environment variables or external service configuration.

## Next Phase Readiness
- `/talents` and `/talents/{id}/products` are live, protected, and data-driven — Phase 2's Pipedrive sync can join deals to talents via `talent_products.pipedrive_product_id` once populated.
- Plan 01-03 (public `/health`, change-password/create-user, 401 redirect) can proceed independently — no shared file conflicts beyond `app/main.py` (already has both auth and talents routers registered before StaticFiles).

---
*Phase: 01-foundation-auth-talent-catalog-health-check*
*Completed: 2026-06-11*
