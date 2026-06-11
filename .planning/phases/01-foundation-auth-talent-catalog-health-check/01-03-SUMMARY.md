---
phase: 01-foundation-auth-talent-catalog-health-check
plan: 03
subsystem: auth
tags: [fastapi, sqlalchemy, pyjwt, pwdlib, health-check, vanilla-js]

# Dependency graph
requires:
  - phase: 01-foundation-auth-talent-catalog-health-check
    provides: "Plan 01 (auth router, security helpers, schemas, conftest fixtures), Plan 02 (talents router registration in main.py)"
provides:
  - "Public GET /health endpoint with SELECT 1 DB connectivity probe, always HTTP 200 (AUTH-03)"
  - "POST /auth/change-password — authenticated password rotation with current-password re-verification (D-11)"
  - "POST /auth/users — authenticated user creation with 409 on duplicate email (D-12)"
  - "frontend/js/auth.js logout() helper using apiFetch + /login.html redirect (D-03)"
affects: [phase-02, phase-07-deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Health endpoints return status info in the response body, never via HTTP error codes, so load balancers checking 2xx don't flap"
    - "Account-mutation endpoints (change-password) re-verify the current credential before applying a change, even when already behind get_current_user"

key-files:
  created:
    - app/routers/health.py
    - tests/test_health.py
  modified:
    - app/auth/router.py
    - app/main.py
    - frontend/js/auth.js
    - tests/test_auth.py

key-decisions:
  - "test_change_password restores the admin password after asserting the rotation, since the test DB is session-scoped (StaticPool) and shared with test_talents.py via the auth_client/seed_test_user fixtures"

patterns-established:
  - "Public unauthenticated routes (health) live in their own router with no get_current_user dependency, registered alongside protected routers but documented as the exception"

requirements-completed: [AUTH-02, AUTH-03]

# Metrics
duration: 14min
completed: 2026-06-11
---

# Phase 1 Plan 03: Health Check, Account Management & 401 Redirect Summary

**Public `/health` liveness probe with always-200 SELECT-1 DB check, plus `/auth/change-password` and `/auth/users` endpoints completing the single-tier auth lifecycle, and a frontend `logout()` helper wired through the existing 401-redirect interceptor.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-06-11T19:29:00Z
- **Completed:** 2026-06-11T19:43:20Z
- **Tasks:** 2 completed
- **Files modified:** 6 (1 created: app/routers/health.py; 1 created: tests/test_health.py; 4 modified: app/auth/router.py, app/main.py, frontend/js/auth.js, tests/test_auth.py)

## Accomplishments
- `GET /health` is public (no auth dependency), runs `db.execute(text("SELECT 1"))`, and always returns HTTP 200 with `{"status": "ok", "database": "ok"|"error"}` (AUTH-03)
- `POST /auth/change-password` re-verifies `current_password` against the stored hash before rotating to `new_password`; wrong current password returns 401; old password stops working immediately after rotation (D-11)
- `POST /auth/users` creates a new user (any authenticated caller, single-tier auth per FUT-03 deferral), returns 201 + `UserRead`, 409 on duplicate email (D-12)
- `app/main.py` now registers all three routers (auth, talents, health) before the StaticFiles mount
- `frontend/js/auth.js` gained a `logout()` helper that POSTs `/auth/logout` via the existing `apiFetch` 401-interceptor, then redirects to `/login.html` (D-03)

## Task Commits

Each task was committed atomically (TDD plan — RED then GREEN):

1. **Task 1 RED: failing tests for health + change-password + create-user** - `9fbdc61` (test)
2. **Task 1 GREEN: health router, change-password/users endpoints, main.py registration** - `2e3eeed` (feat)
3. **Task 2: frontend logout() helper (apiFetch interceptor already present from Plan 01)** - `42c851f` (feat)

**Plan metadata:** (pending — committed by this agent before returning, see below)

## Files Created/Modified
- `app/routers/health.py` - New public router: `GET /health` with SELECT 1 probe, always 200, `{status, database}` body
- `app/auth/router.py` - Added `POST /auth/change-password` and `POST /auth/users` to the existing login/logout/me router
- `app/main.py` - Added `from app.routers import health` and `app.include_router(health.router)` before the StaticFiles mount, alongside the existing auth + talents registrations
- `frontend/js/auth.js` - Added `logout()` helper (apiFetch-based POST to `/auth/logout` + redirect to `/login.html`); existing login form handler and `apiFetch` 401 interceptor (from Plan 01) left intact
- `tests/test_health.py` - New: `test_health_no_auth`, `test_health_db_check`
- `tests/test_auth.py` - Added `test_change_password`, `test_change_password_wrong_current`, `test_create_user`

## Decisions Made
- `test_change_password` restores the admin password (`settings.ADMIN_PASSWORD`) at the end of the test by calling `/auth/change-password` again. The test DB is created once per pytest session (StaticPool, in-memory SQLite) and shared across `test_auth.py` and `test_talents.py` via the `seed_test_user`/`auth_client` fixtures, which only seed the admin user `if user is None`. Without restoring the password, a permanent mutation in one test would break the `auth_client` fixture (and therefore all of `test_talents.py`) for any test that runs afterward. This keeps the new test self-contained without touching the shared `conftest.py` fixtures used by other plans' tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Restored admin password after test_change_password to preserve test-suite isolation**
- **Found during:** Task 1 (GREEN phase — running `uv run pytest tests/test_health.py tests/test_auth.py -x -q`)
- **Issue:** `test_change_password` rotated the shared admin user's password and committed the change to the session-scoped, in-memory test DB. The next test (`test_change_password_wrong_current`) failed at fixture setup: `auth_client` could no longer log in with `settings.ADMIN_PASSWORD` (401 instead of 200), because `seed_test_user` only creates the admin row `if user is None` and does not reset its password.
- **Fix:** Added a third `POST /auth/change-password` call at the end of `test_change_password` that rotates the password back to `settings.ADMIN_PASSWORD`, asserting 200. This restores the shared fixture's invariant for all subsequent tests (including `test_talents.py`, which also depends on `auth_client`).
- **Files modified:** tests/test_auth.py
- **Verification:** `uv run pytest tests/ -v` — all 17 tests pass (10 in test_health.py/test_auth.py, 7 across test_database.py/test_security.py/test_talents.py)
- **Committed in:** `2e3eeed` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug — test isolation)
**Impact on plan:** Necessary for correctness of the full test suite; no scope creep — the fix is confined to the new test added in this plan.

## Issues Encountered
None beyond the auto-fixed test-isolation issue documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 1 foundation is now feature-complete: public `/health` (AUTH-03), full single-tier auth lifecycle (login/logout/me/change-password/users), talent catalog CRUD (Plan 02), and a frontend 401-to-login redirect + logout helper (D-03) ready for Phase 2's dashboard pages to consume via `apiFetch`.
- Full test suite (17 tests across test_auth, test_database, test_health, test_security, test_talents) passes green with no regressions.
- Manual verification of the 401-to-login redirect in a real browser (per VALIDATION.md Manual-Only table) is deferred to the phase checkpoint — no blocker for Phase 2 start.

---
*Phase: 01-foundation-auth-talent-catalog-health-check*
*Completed: 2026-06-11*

## Self-Check: PASSED

- FOUND: app/routers/health.py
- FOUND: tests/test_health.py
- FOUND: .planning/phases/01-foundation-auth-talent-catalog-health-check/01-03-SUMMARY.md
- FOUND: change-password route in app/auth/router.py
- FOUND: include_router(health.router) in app/main.py
- FOUND: logout() helper in frontend/js/auth.js
- FOUND: commits 9fbdc61, 2e3eeed, 42c851f, 41dbb11
