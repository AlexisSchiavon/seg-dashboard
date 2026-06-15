# Phase 1: Foundation — Auth, Talent Catalog & Health Check - Context

**Gathered:** 2026-06-10
**Status:** Ready for planning

<domain>
## Phase Boundary

A runnable FastAPI application with: (1) email/password login issuing a JWT delivered via httpOnly cookie, with protected endpoints rejecting unauthenticated requests; (2) a public `/health` endpoint; (3) a SQLite-backed talent catalog (21 initial talents, seeded by name) that can be listed/added/edited via API without code changes, with each talent mappable to one or more Pipedrive product IDs via a normalized join table. This is the foundation every later module (Pipedrive, Sheets, Trello, AI reports, agent) builds on.

</domain>

<decisions>
## Implementation Decisions

### Authentication & Sessions
- **D-01:** JWT is delivered via a secure httpOnly cookie (server-set on login), NOT via Authorization header + localStorage.
- **D-02:** Session/cookie lifetime is 7 days.
- **D-03:** When the token is missing/expired/invalid (401 from a protected endpoint), the frontend auto-redirects to the login page.
- **D-04:** Login page is a standalone centered card matching the dashboard's dark theme (color palette/typography from `mockup.html`).
- **D-05:** Logout is implemented via `POST /auth/logout`, which clears the auth cookie server-side.
- **D-06:** A failed login attempt returns a generic "Invalid email or password" message (does not reveal whether the email exists).
- **D-07:** No brute-force protection / rate limiting on the login endpoint in Phase 1 — deferred to a later security pass.

### User Provisioning
- **D-08:** The initial user account is created by a seed script that reads admin credentials from `.env` (e.g., `ADMIN_EMAIL` / `ADMIN_PASSWORD`).
- **D-09:** Only ONE account is needed for now ("just me for now") — the seed script creates a single user.
- **D-10:** Re-running the seed script is idempotent: if the user already exists, it UPDATES the existing account's credentials (supports password rotation via `.env` + reseed).
- **D-11:** Authenticated users can change their own password via a change-password endpoint (+ a simple form in the UI).
- **D-12:** Adding future team members (post-Phase-1) goes through a protected admin endpoint (e.g., `POST /auth/users`) — no dedicated UI required for this.

### Talent Catalog Schema
- **D-13:** Each talent record has: `name`, `active` (boolean flag), `category` (niche, e.g. música/fitness/comedia/etc.).
- **D-14:** Pipedrive product ID mapping uses a separate normalized join table (`talent_products`, one-to-many talent→product IDs) — not a comma-separated text field.
- **D-15:** The 21 initial talents (names listed in `PROJECT.md` Context section) are seeded by NAME ONLY. Pipedrive product IDs are left empty/null in Phase 1 — to be filled in once known (Phase 2 territory).

### Claude's Discretion
- **Photo/avatar field for talents** — user said "you decide". Include a nullable `photo_url` field only if it doesn't complicate the schema; no upload pipeline either way in Phase 1.
- **Talent catalog management UI** — this area was offered but the user chose not to discuss it further, and `/gsd:plan-phase` was invoked with `--skip-ui` (no UI design contract for this phase). Default: satisfy TAL-01 ("addable/editable without code changes") via protected CRUD endpoints (`/talents`, `/talents/{id}/products`) — a dedicated Talents admin page is NOT required for Phase 1 unless the planner judges it trivially cheap given the walking-skeleton UI work already needed for login. If a minimal admin UI is added, it should match the dark theme per D-04.
- **`/health` endpoint scope** — whether it includes a DB connectivity check (`SELECT 1`) vs just process-up `200 OK` is left to planner/research (PITFALLS.md recommends a DB check).
- **Cookie implementation details** — cookie name, `SameSite`/`Secure` flag handling for local dev vs prod, follow secure defaults per STACK.md/PITFALLS.md.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Tech Stack & Library Choices
- `.planning/research/STACK.md` — confirms PyJWT (not python-jose) + pwdlib[argon2] (not passlib), SQLAlchemy 2.0 declarative style (`Mapped`/`mapped_column`), Alembic for migrations. Directly governs how auth (D-01–D-12) and the talent/talent_products schema (D-13–D-15) are implemented.

### Architecture
- `.planning/research/ARCHITECTURE.md` — modular FastAPI monolith structure (`app/integrations/`, `app/services/`, `app/routers/`) that Phase 1 must establish for later phases to build on.

### Known Pitfalls
- `.planning/research/PITFALLS.md` — JWT library pitfalls, bcrypt/passlib breakage on Python 3.12, SQLite WAL mode setup. Must be applied during Phase 1 scaffolding.

### UI Reference
- `.planning/reference/mockup.html` — dark mode, mobile-first dashboard mockup. The login page (D-04) should match its color palette and typography. Note: the mockup contains NO existing login or admin UI — these are new for Phase 1.

### Project Constraints
- `CLAUDE.md` — predefined folder structure (`app/main.py`, `app/config.py`, `app/models.py`, `app/database.py`, `app/integrations/`, `app/services/`, `app/routers/`, `frontend/`), required env vars (`SECRET_KEY`, `DATABASE_URL`, etc.), fixed tech stack.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet. The repo currently contains only a default `uv init` scaffold: `main.py` (hello-world), `pyproject.toml` (no dependencies, `requires-python = ">=3.9"`), `.python-version` (3.9 — needs bumping to 3.12 per CLAUDE.md). No `app/` or `frontend/` directories exist.

### Established Patterns
- None yet — Phase 1 establishes the first patterns: FastAPI app structure, SQLAlchemy session-per-request pattern, JWT cookie auth dependency, Alembic migration setup.

### Integration Points
- N/A for Phase 1 (foundation phase). Phase 2+ (Pipedrive/Sheets/Trello) will build on the auth dependency and DB session pattern established here.

</code_context>

<specifics>
## Specific Ideas

- Login page must visually match `mockup.html`'s dark theme (colors/typography) as a standalone centered card (D-04).
- 21 talent names are listed in `PROJECT.md` → Context → "21 talentos actuales" — use this list as the seed data source (D-15).
- `pyproject.toml` / `.python-version` need updating from `3.9` to `3.12` per CLAUDE.md constraints (not a discussion decision, but required for any Phase 1 work to proceed).

</specifics>

<deferred>
## Deferred Ideas

- **Talent catalog admin UI (dedicated page)** — not committed for Phase 1 (see Claude's Discretion above). If deferred past Phase 1, note as a future UI-phase candidate.
- **Photo/avatar uploads** — no upload pipeline; at most a nullable URL field (Claude's discretion).
- **Role-based access control** — confirmed out of scope for the whole project per `PROJECT.md` (tracked as `FUT-03`).

</deferred>

---

*Phase: 1-foundation-auth-talent-catalog-health-check*
*Context gathered: 2026-06-10*
