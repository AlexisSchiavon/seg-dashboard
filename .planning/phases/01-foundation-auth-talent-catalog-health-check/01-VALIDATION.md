---
phase: 01
slug: foundation-auth-talent-catalog-health-check
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-10
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (latest 8.x) + httpx `ASGITransport` / FastAPI `TestClient` |
| **Config file** | none yet — Wave 0 creates `pyproject.toml` `[tool.pytest.ini_options]` (or `pytest.ini`) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~10-20 seconds (SQLite in-memory/test-file, no external network calls in Phase 1) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | AUTH-01 | V2/V3 | Login with correct email/password returns 200 + sets httpOnly `access_token` cookie | integration | `uv run pytest tests/test_auth.py::test_login_success -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | AUTH-01 | V2 (D-06) | Login with wrong password returns 401 with generic "Invalid email or password" (no user enumeration) | integration | `uv run pytest tests/test_auth.py::test_login_invalid_credentials -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | AUTH-02 | V4 | Protected endpoint without cookie returns 401 | integration | `uv run pytest tests/test_auth.py::test_protected_requires_auth -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | AUTH-02 | V3/Tampering | Protected endpoint with expired/invalid JWT returns 401 (explicit `algorithms=["HS256"]` allowlist) | integration | `uv run pytest tests/test_auth.py::test_protected_rejects_invalid_token -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | AUTH-02 | V3 (D-05) | Logout clears cookie server-side; subsequent protected request returns 401 | integration | `uv run pytest tests/test_auth.py::test_logout_clears_session -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | AUTH-02 | — (D-11) | Authenticated user can change their own password via change-password endpoint | integration | `uv run pytest tests/test_auth.py::test_change_password -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | AUTH-03 | — | `GET /health` returns 200 without authentication | integration | `uv run pytest tests/test_health.py::test_health_no_auth -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | AUTH-03 | — | `GET /health` reflects DB connectivity status (`{"database": "ok"|"error"}`) | unit/integration | `uv run pytest tests/test_health.py::test_health_db_check -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TAL-01 | — | Talent CRUD (create/list/edit) works without code changes — 21 seeded talents present | integration | `uv run pytest tests/test_talents.py::test_seeded_talents_present -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TAL-01 | V5 | Adding a new talent via `POST /talents` persists and appears in `GET /talents` (Pydantic validation, 422 on bad input) | integration | `uv run pytest tests/test_talents.py::test_create_talent -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | TAL-02 | V5 | Talent can have one or more `talent_products` rows added/listed via API | integration | `uv run pytest tests/test_talents.py::test_add_talent_product -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | (foundation) | V6 | Password hash/verify roundtrip works on clean install (`pwdlib[argon2]`, Pitfall 1) | unit | `uv run pytest tests/test_security.py::test_password_hash_roundtrip -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | (foundation) | — | SQLite WAL mode + `busy_timeout` pragmas active on engine connection (Pitfall 3) | unit | `uv run pytest tests/test_database.py::test_sqlite_pragmas -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` `[tool.pytest.ini_options]` (or `pytest.ini`) — pytest config + test path, plus bump `requires-python` to `>=3.12` and update `.python-version` to `3.12`
- [ ] `tests/conftest.py` — shared fixtures: test DB engine (separate SQLite file or `:memory:` with `StaticPool`), `TestClient`/`ASGITransport` app fixture, seeded test user fixture
- [ ] `tests/test_auth.py`, `tests/test_health.py`, `tests/test_talents.py`, `tests/test_security.py`, `tests/test_database.py` — all new
- [ ] Framework install: `uv add --dev pytest` (httpx already present transitively via `fastapi[standard]`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Login page renders centered card matching `mockup.html` dark theme (D-04) | AUTH-01 | Visual styling not asserted by integration tests | Run dev server, open `/login`, compare colors/typography/layout against `.planning/reference/mockup.html` |
| 401 from a protected endpoint triggers frontend auto-redirect to `/login` (D-03) | AUTH-02 | Requires browser session/cookie expiry behavior, not just API-level assertion | In browser, clear/expire the auth cookie, navigate to a protected page, confirm redirect to `/login` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
