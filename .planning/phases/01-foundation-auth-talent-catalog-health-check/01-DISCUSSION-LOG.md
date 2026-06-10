# Phase 1: Foundation — Auth, Talent Catalog & Health Check - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-10
**Phase:** 01-foundation-auth-talent-catalog-health-check
**Areas discussed:** Login & session UX, User provisioning, Talent fields & Pipedrive mapping

---

## Login & session UX

| Option | Description | Selected |
|--------|-------------|----------|
| httpOnly cookie | Server sets secure httpOnly cookie; vanilla JS doesn't manage tokens | ✓ |
| Authorization header + localStorage | Frontend stores JWT, attaches as Bearer header | |
| You decide | Claude picks simplest secure option | |

**User's choice:** httpOnly cookie

| Option | Description | Selected |
|--------|-------------|----------|
| 8 hours (workday) | Re-login each morning | |
| 7 days | Long-lived, fewer logins for small trusted team | ✓ |
| You decide | Claude picks reasonable default (~24h) | |

**User's choice:** 7 days

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-redirect to login | 401 -> redirect immediately | ✓ |
| Inline message + re-login button | Banner/toast, no hard redirect | |
| You decide | Claude picks simplest consistent approach | |

**User's choice:** Auto-redirect to login

| Option | Description | Selected |
|--------|-------------|----------|
| Match dashboard dark theme | Standalone centered card, mockup.html palette | ✓ |
| Minimal/unstyled for now | Plain functional form | |
| You decide | Claude picks something easy to restyle | |

**User's choice:** Match dashboard dark theme

---

## User provisioning

| Option | Description | Selected |
|--------|-------------|----------|
| Seed script from .env (Recommended) | Script reads ADMIN_EMAIL/ADMIN_PASSWORD, creates user(s) | ✓ |
| Alembic seed migration | Migration inserts fixed user row(s) | |
| You decide | Claude picks simplest approach | |

**User's choice:** Seed script from .env

| Option | Description | Selected |
|--------|-------------|----------|
| Single shared account | One login for whole team | |
| One per team member | Individual accounts | ✓ |
| You decide | Claude seeds 1-2 placeholders | |

**User's choice:** One per team member -> clarified as "Just me for now" (single account)

| Option | Description | Selected |
|--------|-------------|----------|
| Out of scope for now | Password set via .env/seed only | |
| Include change-password endpoint | Authenticated users update own password via API+form | ✓ |
| You decide | Claude picks based on minimal scope | |

**User's choice:** Include change-password endpoint

| Option | Description | Selected |
|--------|-------------|----------|
| Re-run seed script / DB insert | Admin reruns script or inserts row | |
| Protected admin endpoint | POST /auth/users, no UI | ✓ |
| You decide | Claude picks lowest-effort option | |

**User's choice:** Protected admin endpoint

| Option | Description | Selected |
|--------|-------------|----------|
| Update existing user (Recommended) | Reseed updates existing account | ✓ |
| Error if user exists | Seed script only works once | |
| You decide | Claude picks safest option | |

**User's choice:** Update existing user (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| POST /auth/logout clears cookie (Recommended) | Server-controlled logout | ✓ |
| Client-side only | Cookie remains valid until expiry | |
| You decide | Claude picks consistent approach | |

**User's choice:** POST /auth/logout clears cookie (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Generic 'Invalid email or password' (Recommended) | Doesn't reveal account existence | ✓ |
| Specific error (email not found vs wrong password) | More helpful, reveals existence | |
| You decide | Claude picks standard security practice | |

**User's choice:** Generic 'Invalid email or password' (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| None for now (Recommended) | Defer rate limiting | ✓ |
| Basic rate limiting | Max N attempts per IP/window | |
| You decide | Claude picks based on MVP scope | |

**User's choice:** None for now (Recommended)

---

## Talent fields & Pipedrive mapping

| Option | Description | Selected |
|--------|-------------|----------|
| Name + active flag only | Minimal roster management | |
| Name + active flag + category | Adds category/niche field | ✓ |
| You decide | Claude picks minimal fields | |

**User's choice:** Name + active flag + category

| Option | Description | Selected |
|--------|-------------|----------|
| Comma-separated text field | Simple string field | |
| Separate join table (talent_products) | Normalized one-to-many | ✓ |
| You decide | Claude picks cleanest for SQLAlchemy + Pipedrive sync | |

**User's choice:** Separate join table (talent_products)

| Option | Description | Selected |
|--------|-------------|----------|
| No photo for now | Just name + fields above | |
| Add optional photo URL field | Nullable field in schema | |
| You decide | Claude picks based on schema needs | ✓ |

**User's choice:** You decide (Claude's discretion)

| Option | Description | Selected |
|--------|-------------|----------|
| Seed with names only (Recommended) | Pipedrive IDs left empty/null | ✓ |
| I'll provide product ID mapping now | User supplies IDs for seed data | |
| You decide | Claude seeds names only | |

**User's choice:** Seed with names only (Recommended)

---

## Claude's Discretion

- Photo/avatar field for talents (nullable, optional)
- Talent catalog management UI — whether Phase 1 needs a dedicated admin page beyond CRUD endpoints (consistent with `--skip-ui` on plan-phase)
- `/health` endpoint scope (process-up only vs DB connectivity check)
- Cookie implementation details (name, SameSite/Secure flags for dev vs prod)

## Deferred Ideas

- Talent catalog admin UI (dedicated page) — possible future UI-phase candidate
- Photo/avatar uploads (no upload pipeline)
- Role-based access control — already tracked as FUT-03 in REQUIREMENTS.md, confirmed out of scope
