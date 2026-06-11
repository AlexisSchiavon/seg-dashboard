# Walking Skeleton — SEG Talent Intelligence Dashboard

**Phase:** 1
**Generated:** 2026-06-10

## Capability Proven End-to-End

A user opens the dark-theme login page, submits the seeded admin credentials, the server verifies them (pwdlib[argon2]), issues a PyJWT HS256 token set as an httpOnly cookie, and a protected endpoint (`GET /auth/me`) then accepts that cookie and returns the user — while rejecting any request without a valid cookie (401). This single round-trip exercises the full stack: Vanilla-JS UI → FastAPI route → pydantic-settings config → SQLAlchemy 2.0 + SQLite (WAL) → Alembic-migrated schema → seeded admin user.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | FastAPI 0.136.x (`fastapi[standard]`), Uvicorn ASGI | Fixed by CLAUDE.md; routers/services/integrations layout maps to FastAPI dependency injection |
| Runtime | Python 3.12 (bumped from the repo's 3.9 scaffold) | CLAUDE.md constraint; several deps require >=3.10 (RESEARCH.md Pitfall 6 — hard blocker, done first) |
| Data layer | SQLite via SQLAlchemy 2.0 declarative (`Mapped`/`mapped_column`), sync engine | Fixed by CLAUDE.md; WAL + busy_timeout=10000 configured via a `connect` event listener from commit 1 (Pitfall 3) |
| Migrations | Alembic 1.18.x, sync engine, `target_metadata = Base.metadata` | Versioned schema evolution needed from Phase 2 onward; single `Base` declared in app/database.py |
| Auth | JWT (PyJWT, HS256) in an httpOnly + SameSite=Lax cookie; pwdlib[argon2] for password hashing; single-tier (no RBAC, FUT-03 deferred) | D-01 (cookie not localStorage), D-02 (7-day expiry); PyJWT/pwdlib chosen over python-jose/passlib (Python 3.12 breakage) |
| Cookie Secure flag | `COOKIE_SECURE` env var (default True), set False for local http dev | Pitfall 4 — hardcoded `secure=True` silently breaks local http login |
| Config | pydantic-settings `BaseSettings`, fail-fast on missing SECRET_KEY, all CLAUDE.md env vars defined (M2-M5 as empty placeholders) | Catches missing secrets at startup; one source of truth |
| Deployment target | Local `uv run uvicorn app.main:app` for Phase 1; Docker + EasyPanel deferred to Phase 7 | Walking Skeleton proves stack via documented local full-stack run; deploy is its own milestone |
| Directory layout | `app/{config,database,models,main}.py` + `app/{auth,routers,schemas,scripts,integrations}/` packages; `frontend/`; `alembic/`; `tests/` | Fixed by CLAUDE.md, extended with auth/schemas/scripts per ARCHITECTURE.md |
| Frontend | HTML + CSS + Vanilla JS, dark mode, mobile-first; design tokens from `.planning/reference/mockup.html` | Fixed by CLAUDE.md (no JS frameworks); login page is a standalone centered card (D-04) |
| Tests | pytest + FastAPI TestClient / httpx ASGITransport; isolated test DB | Validation strategy (01-VALIDATION.md); Wave 0 scaffolding created in Plan 01 |

## Stack Touched in Phase 1

- [x] Project scaffold (Python 3.12 pin, `fastapi[standard]` + deps via uv, ruff, pytest config) — Plan 01 Task 0/1
- [x] Routing — `/auth/login`, `/auth/logout`, `/auth/me` (Plan 01); `/talents/*` (Plan 02); `/health`, `/auth/change-password`, `/auth/users` (Plan 03)
- [x] Database — real write (admin seed, talent seed, create endpoints) AND real read (login lookup, list endpoints, SELECT 1 health probe)
- [x] UI — login form wired to `/auth/login` setting the cookie; 401 → login redirect interceptor (Plan 03)
- [x] Deployment — documented local full-stack run: `uv run uvicorn app.main:app` after `alembic upgrade head` + `python -m app.scripts.seed_admin`

## Out of Scope (Deferred to Later Slices)

- Pipedrive/Sheets/Trello sync and any integration code (Phases 2-4) — `app/integrations/` is an empty placeholder package only
- Dashboard tabs (Resumen, Por talento, Funnel, Leads, Reportes) — Phase 2+
- Dedicated talent admin UI page — TAL-01 satisfied via protected CRUD endpoints only (CONTEXT.md Claude's Discretion); a UI page is not built in Phase 1
- Photo/avatar upload pipeline — only a nullable `photo_url` column exists (no upload)
- Rate limiting / brute-force protection on login (D-07), full CSRF token scheme — deferred security pass; SameSite=Lax included as near-zero-cost mitigation
- Role-based access control (FUT-03) — single auth tier; any authenticated user has full access
- Docker / EasyPanel deployment + `/data/seg.db` absolute path + persistent volume (Phase 7)
- Pipedrive product IDs are left null on seeded talents (D-15) — filled in Phase 2

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions (auth cookie, single Base, WAL SQLite, sync SQLAlchemy, Alembic, services layer as single source of truth for figures):

- Phase 2: Pipedrive deal sync → Resumen, Por talento, Funnel tabs with real revenue/funnel data (populates talent product IDs)
- Phase 3: Google Sheets leads sync → Leads tab
- Phase 4: Trello campaign/collection sync + Pipedrive→Trello automation → completes Por talento revenue projection
- Phase 5: Claude-narrated PDF monthly reports + Reportes tab (figures computed in Python services, AI narrates only)
- Phase 6: Embedded read-only NL agent (tool-calling against the existing services layer)
- Phase 7: Docker + EasyPanel deployment with persistent SQLite volume verified across redeploys
